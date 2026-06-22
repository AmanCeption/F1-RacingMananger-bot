"""
Game Services Layer
Handles all business logic for the F1 Management Game
"""
import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func

from src.models.models import (
    User, Team, League, Driver, TeamDriver, Staff, TeamStaff,
    Race, RaceResult, RaceStrategy, QualifyingResult, Season,
    DriverStanding, ConstructorStanding, DriverTransfer, Sponsor,
    TeamSponsor, ResearchProject, Achievement, TeamAchievement,
    AdminLog, SuspiciousActivity, LeagueStatus, RaceStatus, TransferStatus
)
from src.core.config import settings, F1_POINTS, F1_CALENDAR
from src.simulation.driver_db import REAL_DRIVERS, FICTIONAL_DRIVERS, STAFF_DATABASE, SPONSORS, ACHIEVEMENTS, RESEARCH_TREES
from src.simulation.race_engine import (
    CarEntry, simulate_race, simulate_qualifying, generate_practice_report,
    generate_weather, Weather, generate_staff_race_insights
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# USER SERVICE
# ─────────────────────────────────────────────

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: int, username: str, first_name: str) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(id=user_id, username=username, first_name=first_name)
            self.db.add(user)
            await self.db.flush()
        return user

    async def get(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def is_banned(self, user_id: int) -> bool:
        user = await self.get(user_id)
        return user.is_banned if user else False

    async def claim_daily(self, user_id: int) -> Optional[dict]:
        user = await self.get(user_id)
        if not user:
            return None

        now = datetime.utcnow()
        if user.last_daily and (now - user.last_daily).total_seconds() < 86400:
            remaining = 86400 - (now - user.last_daily).total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return {"available": False, "hours": hours, "minutes": minutes}

        # Get team for reward
        team_result = await self.db.execute(
            select(Team).where(Team.owner_id == user_id)
        )
        team = team_result.scalar_one_or_none()

        reward_money = settings.DAILY_REWARD_MONEY
        reward_rp = settings.DAILY_REWARD_RP

        if team:
            team.budget += reward_money
            team.research_points += reward_rp

        user.last_daily = now
        await self.db.flush()

        return {
            "available": True,
            "money": reward_money,
            "rp": reward_rp,
        }


# ─────────────────────────────────────────────
# TEAM SERVICE
# ─────────────────────────────────────────────

class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner_id: int, name: str, logo_url: Optional[str] = None) -> Team:
        # Check if already has a team
        existing = await self.db.execute(
            select(Team).where(Team.owner_id == owner_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("You already have a team!")

        team = Team(
            owner_id=owner_id,
            name=name,
            logo_url=logo_url,
            budget=settings.STARTING_BUDGET,
        )
        self.db.add(team)
        await self.db.flush()
        return team

    async def check_name_in_league(self, league_id: int, name: str, exclude_team_id: int = None) -> bool:
        """Returns True if name already taken in this league"""
        q = select(Team).where(
            and_(Team.league_id == league_id,
                 func.lower(Team.name) == name.lower().strip())
        )
        if exclude_team_id:
            q = q.where(Team.id != exclude_team_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def get_by_owner(self, owner_id: int) -> Optional[Team]:
        result = await self.db.execute(
            select(Team).where(Team.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def get(self, team_id: int) -> Optional[Team]:
        result = await self.db.execute(select(Team).where(Team.id == team_id))
        return result.scalar_one_or_none()

    async def get_with_drivers(self, team_id: int) -> dict:
        team = await self.get(team_id)
        if not team:
            return {}

        drivers_result = await self.db.execute(
            select(TeamDriver, Driver)
            .join(Driver, TeamDriver.driver_id == Driver.id)
            .where(TeamDriver.team_id == team_id)
        )
        drivers = [{"contract": td, "driver": d} for td, d in drivers_result.all()]

        staff_result = await self.db.execute(
            select(TeamStaff, Staff)
            .join(Staff, TeamStaff.staff_id == Staff.id)
            .where(TeamStaff.team_id == team_id)
        )
        staff = [{"contract": ts, "staff": s} for ts, s in staff_result.all()]

        sponsors_result = await self.db.execute(
            select(TeamSponsor, Sponsor)
            .join(Sponsor, TeamSponsor.sponsor_id == Sponsor.id)
            .where(and_(TeamSponsor.team_id == team_id, TeamSponsor.is_active == True))
        )
        sponsors = [{"contract": tsp, "sponsor": sp} for tsp, sp in sponsors_result.all()]

        return {
            "team": team,
            "drivers": drivers,
            "staff": staff,
            "sponsors": sponsors,
        }

    async def upgrade_car(self, team_id: int, stat: str, amount: int, cost: int) -> bool:
        team = await self.get(team_id)
        if not team or team.budget < cost:
            return False

        current = getattr(team, stat, 0)
        if current >= 100:
            raise ValueError(f"{stat} is already maxed at 100!")

        new_val = min(100, current + amount)
        setattr(team, stat, new_val)
        team.budget -= cost
        await self.db.flush()
        return True

    async def upgrade_facility(self, team_id: int, facility: str) -> tuple[bool, str]:
        team = await self.get(team_id)
        if not team:
            return False, "Team not found"

        attr = f"{facility}_level"
        current = getattr(team, attr, 0)
        if current >= 5:
            return False, f"{facility.replace('_', ' ').title()} is already at max level!"

        costs = {1: 10_000_000, 2: 25_000_000, 3: 50_000_000, 4: 100_000_000}
        cost = costs.get(current, 100_000_000)

        if team.budget < cost:
            return False, f"Need ${cost:,} but you only have ${team.budget:,}"

        team.budget -= cost
        setattr(team, attr, current + 1)
        await self.db.flush()
        return True, f"Upgraded to Level {current + 1}!"


    async def delete(self, owner_id: int) -> tuple[bool, str]:
        team = await self.get_by_owner(owner_id)
        if not team:
            return False, "Team not found!"
        # Allow delete anytime — team leaves league automatically
        await self.db.delete(team)
        await self.db.flush()
        return True, "Team deleted."

    async def rename(self, owner_id: int, new_name: str) -> tuple[bool, str]:
        if len(new_name) < 3:
            return False, "Name too short! Min 3 characters."
        if len(new_name) > 30:
            return False, "Name too long! Max 30 characters."
        team = await self.get_by_owner(owner_id)
        if not team:
            return False, "Team not found!"

        # Check name not taken in same league
        if team.league_id:
            dup = await self.db.execute(
                select(Team).where(
                    and_(Team.league_id == team.league_id,
                         func.lower(Team.name) == new_name.lower().strip(),
                         Team.id != team.id)
                )
            )
            if dup.scalar_one_or_none():
                return False, f"Team name '{new_name}' already exists in this league! Please choose another name."

        # Check global name uniqueness
        dup_global = await self.db.execute(
            select(Team).where(
                and_(func.lower(Team.name) == new_name.lower().strip(),
                     Team.id != team.id)
            )
        )
        if dup_global.scalar_one_or_none():
            return False, f"Team name '{new_name}' is already taken! Please choose another name."

        team.name = new_name
        await self.db.flush()
        return True, new_name

    async def set_car_setup(self, team_id: int, driver_id: int, setup: dict, race_id: int) -> bool:
        # Store in race strategy
        existing = await self.db.execute(
            select(RaceStrategy).where(
                and_(RaceStrategy.race_id == race_id, RaceStrategy.team_id == team_id,
                     RaceStrategy.driver_id == driver_id)
            )
        )
        strat = existing.scalar_one_or_none()
        if strat:
            strat.car_setup = setup
        else:
            strat = RaceStrategy(
                race_id=race_id, team_id=team_id, driver_id=driver_id,
                strategy_type="balanced", starting_tyre="medium", car_setup=setup
            )
            self.db.add(strat)
        await self.db.flush()
        return True


# ─────────────────────────────────────────────
# LEAGUE SERVICE
# ─────────────────────────────────────────────

class LeagueService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_invite_code(self) -> str:
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(8))

    async def create(self, owner_id: int, name: str, description: str = "",
                     is_public: bool = True, password: str = None) -> League:
        existing = await self.db.execute(select(League).where(League.name == name))
        if existing.scalar_one_or_none():
            raise ValueError("League name already taken!")

        league = League(
            name=name,
            description=description,
            owner_id=owner_id,
            invite_code=self._generate_invite_code(),
            is_public=is_public,
            password=password,
        )
        self.db.add(league)
        await self.db.flush()
        return league

    async def get_by_invite(self, invite_code: str) -> Optional[League]:
        result = await self.db.execute(
            select(League).where(League.invite_code == invite_code.upper())
        )
        return result.scalar_one_or_none()

    async def join(self, team_id: int, invite_code: str, password: str = None) -> tuple[bool, str]:
        league = await self.get_by_invite(invite_code)
        if not league:
            return False, "Invalid invite code!"

        if league.status not in [LeagueStatus.WAITING]:
            return False, "League season has already started!"

        if league.password and league.password != password:
            return False, "Wrong password!"

        # Count teams
        teams_result = await self.db.execute(
            select(func.count(Team.id)).where(Team.league_id == league.id)
        )
        count = teams_result.scalar()
        if count >= league.max_teams:
            return False, f"League is full! ({league.max_teams} teams max)"

        team = await TeamService(self.db).get(team_id)
        if not team:
            return False, "Team not found!"

        if team.league_id:
            return False, "You're already in a league!"

        team.league_id = league.id
        await self.db.flush()
        return True, f"Joined league: {league.name}!"

    async def start_season(self, league_id: int, owner_id: int) -> tuple[bool, str]:
        result = await self.db.execute(select(League).where(League.id == league_id))
        league = result.scalar_one_or_none()
        if not league or league.owner_id != owner_id:
            return False, "Permission denied!"

        if league.status == LeagueStatus.ACTIVE:
            return False, "Season already running! Race using /forcerace."

        teams_result = await self.db.execute(
            select(func.count(Team.id)).where(Team.league_id == league_id)
        )
        count = teams_result.scalar()
        if count < 2:
            return False, "Need at least 2 teams to start!"

        # Clean up any leftover SCHEDULED races from previous failed starts
        from sqlalchemy import delete as sa_delete
        await self.db.execute(
            sa_delete(Race).where(
                and_(Race.league_id == league_id, Race.status == RaceStatus.SCHEDULED)
            )
        )
        await self.db.flush()

        # Create races
        for i, track in enumerate(F1_CALENDAR[:settings.SEASON_RACES]):
            race = Race(
                league_id=league_id,
                season=league.current_season,
                round=i + 1,
                name=track["name"],
                circuit=track["circuit"],
                country=track["country"],
                laps=track["laps"],
            )
            self.db.add(race)

        league.status = LeagueStatus.ACTIVE
        season = Season(league_id=league_id, season_number=league.current_season)
        self.db.add(season)
        await self.db.flush()
        return True, f"Season {league.current_season} started with {count} teams and {settings.SEASON_RACES} races!"

    async def list_public(self) -> list[League]:
        result = await self.db.execute(
            select(League).where(
                and_(League.is_public == True, League.status.in_([LeagueStatus.WAITING, LeagueStatus.ACTIVE]))
            ).limit(10)
        )
        return result.scalars().all()

    async def leave(self, team_id: int, force: bool = False) -> tuple[bool, str]:
        team = await TeamService(self.db).get(team_id)
        if not team or not team.league_id:
            return False, "You are not in any league!"

        result = await self.db.execute(select(League).where(League.id == team.league_id))
        league = result.scalar_one_or_none()
        if not league:
            return False, "League not found!"

        if league.owner_id == team.owner_id:
            return False, "You are the league owner! Delete the league first."

        team.league_id = None
        await self.db.flush()
        return True, f"You have left {league.name}."

    async def delete(self, owner_id: int, league_id: int, force: bool = False) -> tuple[bool, str]:
        result = await self.db.execute(select(League).where(League.id == league_id))
        league = result.scalar_one_or_none()
        if not league:
            return False, "League not found!"
        if league.owner_id != owner_id:
            return False, "You are not the league owner!"
        if league.status == LeagueStatus.ACTIVE and not force:
            return False, "Cannot delete a league during an active season!"

        # 1. Standings delete karo (league_id FK block karta hai)
        await self.db.execute(delete(DriverStanding).where(DriverStanding.league_id == league_id))
        await self.db.execute(delete(ConstructorStanding).where(ConstructorStanding.league_id == league_id))

        # 2. Race results/strategies/qualifying delete karo
        race_ids_result = await self.db.execute(
            select(Race.id).where(Race.league_id == league_id)
        )
        race_ids = [r[0] for r in race_ids_result.fetchall()]
        if race_ids:
            await self.db.execute(delete(RaceResult).where(RaceResult.race_id.in_(race_ids)))
            await self.db.execute(delete(RaceStrategy).where(RaceStrategy.race_id.in_(race_ids)))
            await self.db.execute(delete(QualifyingResult).where(QualifyingResult.race_id.in_(race_ids)))

        # 3. Races delete karo
        await self.db.execute(delete(Race).where(Race.league_id == league_id))

        # 4. Seasons delete karo
        await self.db.execute(delete(Season).where(Season.league_id == league_id))

        # 5. Teams ko league se detach karo
        await self.db.execute(
            update(Team).where(Team.league_id == league_id).values(league_id=None)
        )

        # 6. League delete karo
        await self.db.delete(league)
        await self.db.flush()
        await self.db.commit()
        return True, f"League '{league.name}' deleted."


# ─────────────────────────────────────────────
# DRIVER MARKET SERVICE
# ─────────────────────────────────────────────

class DriverMarketService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_free_agents(self) -> list[Driver]:
        result = await self.db.execute(
            select(Driver).where(Driver.is_free_agent == True).order_by(Driver.skill.desc())
        )
        return result.scalars().all()

    async def get_transfer_listings(self) -> list:
        result = await self.db.execute(
            select(DriverTransfer, Driver, Team)
            .join(Driver, DriverTransfer.driver_id == Driver.id)
            .outerjoin(Team, DriverTransfer.selling_team_id == Team.id)
            .where(DriverTransfer.status == TransferStatus.PENDING)
        )
        return result.all()

    async def buy_driver(self, team_id: int, driver_id: int, agreed_salary: int = None) -> tuple[bool, str]:
        team = await TeamService(self.db).get(team_id)
        if not team:
            return False, "Team not found!"

        # Check current drivers
        drivers_result = await self.db.execute(
            select(TeamDriver).where(TeamDriver.team_id == team_id)
        )
        drivers = drivers_result.scalars().all()
        if len(drivers) >= 2:
            return False, "You already have 2 drivers! Sell one first."

        driver_result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
        driver = driver_result.scalar_one_or_none()
        if not driver:
            return False, "Driver not found!"
        if not driver.is_free_agent:
            return False, "Driver is not a free agent!"

        # Check driver not already in same league (different team)
        if team.league_id:
            league_teams_res = await self.db.execute(
                select(Team.id).where(Team.league_id == team.league_id)
            )
            league_team_ids = [r[0] for r in league_teams_res.fetchall()]
            if league_team_ids:
                dup_res = await self.db.execute(
                    select(TeamDriver).where(
                        and_(TeamDriver.driver_id == driver_id,
                             TeamDriver.team_id.in_(league_team_ids))
                    )
                )
                if dup_res.scalar_one_or_none():
                    return False, f"❌ {driver.name} is already signed by another team in this league!"

        salary = agreed_salary or driver.base_salary

        if team.budget < salary:
            return False, f"Insufficient funds! Need ${salary:,} for first year salary."

        # Sign driver
        contract = TeamDriver(
            team_id=team_id,
            driver_id=driver_id,
            salary=salary,
            contract_years=1,
            is_primary=len(drivers) == 0,
        )
        driver.is_free_agent = False
        self.db.add(contract)
        await self.db.flush()
        return True, f"Signed {driver.name} for ${salary:,}/year!"

    async def sell_driver(self, team_id: int, driver_id: int, asking_price: int = 0,
                          is_auction: bool = False) -> tuple[bool, str]:
        contract_result = await self.db.execute(
            select(TeamDriver).where(
                and_(TeamDriver.team_id == team_id, TeamDriver.driver_id == driver_id)
            )
        )
        contract = contract_result.scalar_one_or_none()
        if not contract:
            return False, "This driver is not on your team!"

        driver_result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
        driver = driver_result.scalar_one_or_none()

        # Create listing
        listing = DriverTransfer(
            driver_id=driver_id,
            selling_team_id=team_id,
            asking_price=asking_price,
            is_auction=is_auction,
            auction_end=datetime.utcnow() + timedelta(hours=24) if is_auction else None,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        self.db.add(listing)

        # Remove from team
        await self.db.delete(contract)
        driver.is_free_agent = True
        await self.db.flush()
        return True, f"{driver.name} listed {'for auction' if is_auction else f'at ${asking_price:,}'}!"

    async def place_bid(self, team_id: int, transfer_id: int, bid: int) -> tuple[bool, str]:
        transfer_result = await self.db.execute(
            select(DriverTransfer).where(DriverTransfer.id == transfer_id)
        )
        transfer = transfer_result.scalar_one_or_none()
        if not transfer or not transfer.is_auction:
            return False, "Auction not found!"
        if transfer.status != TransferStatus.PENDING:
            return False, "Auction has ended!"
        if transfer.auction_end and datetime.utcnow() > transfer.auction_end:
            return False, "Auction has expired!"
        if bid <= (transfer.highest_bid or 0):
            return False, f"Bid must be higher than current: ${transfer.highest_bid:,}"

        team = await TeamService(self.db).get(team_id)
        if team.budget < bid:
            return False, "Insufficient funds!"

        transfer.highest_bid = bid
        transfer.highest_bidder_id = team_id
        await self.db.flush()
        return True, f"Bid of ${bid:,} placed!"


# ─────────────────────────────────────────────
# RACE SERVICE
# ─────────────────────────────────────────────

class RaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_next_race(self, league_id: int) -> Optional[Race]:
        result = await self.db.execute(
            select(Race).where(
                and_(Race.league_id == league_id,
                     Race.status.in_([RaceStatus.SCHEDULED, RaceStatus.QUALIFYING]))
            ).order_by(Race.round.asc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_race(self, race_id: int) -> Optional[Race]:
        result = await self.db.execute(select(Race).where(Race.id == race_id))
        return result.scalar_one_or_none()

    async def set_strategy(self, team_id: int, driver_id: int, race_id: int,
                           strategy: str, tyre: str) -> tuple[bool, str]:
        valid_strategies = ["1stop", "2stop", "3stop", "aggressive", "balanced", "conservative"]
        valid_tyres = ["soft", "medium", "hard"]
        if strategy not in valid_strategies:
            return False, f"Invalid strategy! Choose: {', '.join(valid_strategies)}"
        if tyre not in valid_tyres:
            return False, "Invalid starting tyre! Choose: soft, medium, or hard"

        existing = await self.db.execute(
            select(RaceStrategy).where(
                and_(RaceStrategy.race_id == race_id, RaceStrategy.team_id == team_id,
                     RaceStrategy.driver_id == driver_id)
            )
        )
        strat = existing.scalar_one_or_none()
        if strat:
            strat.strategy_type = strategy
            strat.starting_tyre = tyre
        else:
            strat = RaceStrategy(
                race_id=race_id, team_id=team_id, driver_id=driver_id,
                strategy_type=strategy, starting_tyre=tyre
            )
            self.db.add(strat)
        await self.db.flush()
        return True, f"Strategy set: {strategy.upper()} starting on {tyre.title()} tyres!"

    async def run_qualifying(self, league_id: int) -> Optional[dict]:
        """Run Q1/Q2/Q3 qualifying for the next scheduled race. Saves grid to QualifyingResult."""
        race = await self.get_next_race(league_id)
        if not race:
            return None

        from src.simulation.race_engine import generate_weather, CarEntry, simulate_qualifying, Weather

        weather_val = race.weather  # may already be set from practice
        if weather_val:
            weather = Weather(weather_val)
        else:
            weather = generate_weather()
            race.weather = weather.value

        await self.db.flush()

        # Build entries
        entries = []
        teams_result = await self.db.execute(select(Team).where(Team.league_id == league_id))
        teams = teams_result.scalars().all()

        for team in teams:
            drivers_result = await self.db.execute(
                select(TeamDriver, Driver)
                .join(Driver, TeamDriver.driver_id == Driver.id)
                .where(TeamDriver.team_id == team.id)
            )
            staff_result = await self.db.execute(
                select(TeamStaff, Staff)
                .join(Staff, TeamStaff.staff_id == Staff.id)
                .where(TeamStaff.team_id == team.id)
            )
            staff_list = staff_result.all()
            staff_mod = 1.0
            for ts, s in staff_list:
                staff_mod *= s.performance_bonus
            staff_mod = min(1.25, staff_mod)

            for td, d in drivers_result.all():
                # Check if player set a custom car setup
                strat_result = await self.db.execute(
                    select(RaceStrategy).where(
                        and_(RaceStrategy.race_id == race.id,
                             RaceStrategy.team_id == team.id,
                             RaceStrategy.driver_id == d.id)
                    )
                )
                strat = strat_result.scalar_one_or_none()
                setup = strat.car_setup or {} if strat else {}

                entry = CarEntry(
                    team_id=team.id,
                    team_name=team.name,
                    driver_id=d.id,
                    driver_name=d.name,
                    pace=d.pace,
                    racecraft=d.racecraft,
                    consistency=d.consistency,
                    wet_weather=d.wet_weather,
                    overtaking=d.overtaking,
                    defence=d.defence,
                    engine=team.engine,
                    aerodynamics=team.aerodynamics,
                    chassis=team.chassis,
                    reliability=team.reliability,
                    tyre_mgmt=team.tyres,
                    pit_crew=team.pit_crew,
                    staff_modifier=staff_mod,
                    wing_angle=setup.get("wing_angle", 0),
                    suspension=setup.get("suspension", 0),
                    tyre_pressure=setup.get("tyre_pressure", 0),
                    gear_ratio=setup.get("gear_ratio", 0),
                )
                entries.append(entry)

        if not entries:
            return None

        import asyncio
        result = await asyncio.to_thread(simulate_qualifying, entries, weather, race.circuit)

        # Clear old qualifying results for this race
        await self.db.execute(
            delete(QualifyingResult).where(QualifyingResult.race_id == race.id)
        )

        # Save grid positions
        for car in result["grid"]:
            qt = result["q_times"].get(car.driver_id, {})
            qr = QualifyingResult(
                race_id=race.id,
                team_id=car.team_id,
                driver_id=car.driver_id,
                grid_position=car.position,
                q1_time=qt.get("q1"),
                q2_time=qt.get("q2"),
                q3_time=qt.get("q3"),
            )
            self.db.add(qr)

        # Mark race as qualifying status
        race.status = RaceStatus.QUALIFYING
        await self.db.flush()

        # Format grid for response
        grid_formatted = []
        for car in result["grid"]:
            qt = result["q_times"].get(car.driver_id, {})
            best_time = qt.get("q3") or qt.get("q2") or qt.get("q1")
            grid_formatted.append({
                "position": car.position,
                "driver": car.driver_name,
                "team": car.team_name,
                "q1": qt.get("q1"),
                "q2": qt.get("q2"),
                "q3": qt.get("q3"),
                "best_time": best_time,
            })

        return {
            "race_name": race.name,
            "circuit": race.circuit,
            "country": race.country,
            "weather": weather.value,
            "events": result["events"],
            "grid": grid_formatted,
            "pole_time": result["pole_time"],
            "pole_sitter": result["pole_sitter"],
        }

    async def run_race(self, league_id: int) -> Optional[dict]:
        """Execute next race for a league"""
        race = await self.get_next_race(league_id)
        if not race:
            return None

        race.status = RaceStatus.RACING
        race.started_at = datetime.utcnow()
        weather = generate_weather()
        race.weather = weather.value
        await self.db.flush()

        # Build car entries
        entries = []
        teams_result = await self.db.execute(
            select(Team).where(Team.league_id == league_id)
        )
        teams = teams_result.scalars().all()

        for team in teams:
            drivers_result = await self.db.execute(
                select(TeamDriver, Driver)
                .join(Driver, TeamDriver.driver_id == Driver.id)
                .where(TeamDriver.team_id == team.id)
            )
            team_drivers = drivers_result.all()

            # Staff modifier
            staff_result = await self.db.execute(
                select(TeamStaff, Staff)
                .join(Staff, TeamStaff.staff_id == Staff.id)
                .where(TeamStaff.team_id == team.id)
            )
            staff_list = staff_result.all()
            staff_mod = 1.0
            for ts, s in staff_list:
                staff_mod *= s.performance_bonus
            staff_mod = min(1.25, staff_mod)  # cap at 25% bonus

            for td, d in team_drivers:
                # Get strategy
                strat_result = await self.db.execute(
                    select(RaceStrategy).where(
                        and_(RaceStrategy.race_id == race.id,
                             RaceStrategy.team_id == team.id,
                             RaceStrategy.driver_id == d.id)
                    )
                )
                strat = strat_result.scalar_one_or_none()

                setup = strat.car_setup or {} if strat else {}

                entry = CarEntry(
                    team_id=team.id,
                    team_name=team.name,
                    driver_id=d.id,
                    driver_name=d.name,
                    pace=d.pace,
                    racecraft=d.racecraft,
                    consistency=d.consistency,
                    wet_weather=d.wet_weather,
                    overtaking=d.overtaking,
                    defence=d.defence,
                    engine=team.engine,
                    aerodynamics=team.aerodynamics,
                    chassis=team.chassis,
                    reliability=team.reliability,
                    tyre_mgmt=team.tyres,
                    pit_crew=team.pit_crew,
                    staff_modifier=staff_mod,
                    strategy=strat.strategy_type if strat else "balanced",
                    current_tyre=strat.starting_tyre if strat else "medium",
                    wing_angle=setup.get("wing_angle", 0),
                    suspension=setup.get("suspension", 0),
                    tyre_pressure=setup.get("tyre_pressure", 0),
                    gear_ratio=setup.get("gear_ratio", 0),
                )
                entries.append(entry)

        if not entries:
            return None

        # ── Respect qualifying grid order if it exists ──
        grid_result = await self.db.execute(
            select(QualifyingResult)
            .where(QualifyingResult.race_id == race.id)
            .order_by(QualifyingResult.grid_position.asc())
        )
        grid_rows = grid_result.scalars().all()
        if grid_rows:
            grid_map = {row.driver_id: row.grid_position for row in grid_rows}
            entries.sort(key=lambda e: grid_map.get(e.driver_id, 999))
            for i, entry in enumerate(entries):
                entry.position = i + 1

        # Run simulation in background thread (CPU-bound — must not block the event loop)
        import asyncio
        result = await asyncio.to_thread(simulate_race, entries, race.circuit, race.laps, weather)

        # ── Step 1: Save results & update standings ──────────────────────────
        await self._save_race_results(race, teams, league_id, result)

        # ── Step 2: Award prize money ─────────────────────────────────────────
        await self._award_prize_money(teams, result)

        # ── Step 3: Process sponsors (independent — failure must not kill race) ──
        try:
            await self._process_all_sponsors(result)
        except Exception as e:
            logger.error(f"Sponsor processing failed for race {race.id}: {e}")

        # ── Step 4: Check achievements (independent) ──────────────────────────
        try:
            await self._check_all_achievements(result)
        except Exception as e:
            logger.error(f"Achievement check failed for race {race.id}: {e}")

        # ── Step 5: Mark race finished & generate staff insights ──────────────
        race.status = RaceStatus.FINISHED
        race.finished_at = datetime.utcnow()
        race.race_log = result["events"]

        team_insights = await self._generate_staff_insights(teams, result, league_id)
        result["staff_insights"] = team_insights

        # ── Step 6: Advance league race counter / end season ──────────────────
        league_result = await self.db.execute(select(League).where(League.id == league_id))
        league = league_result.scalar_one_or_none()
        if league:
            league.current_race += 1
            if league.current_race >= settings.SEASON_RACES:
                await self._end_season(league)

        await self.db.flush()

        # Format result for handler
        formatted_results = [
            {
                "position": car.position if not car.is_dnf else None,
                "driver": car.driver_name,
                "team": car.team_name,
                "points": F1_POINTS.get(car.position, 0) if not car.is_dnf else 0,
                "dnf": car.is_dnf,
                "dnf_reason": car.dnf_reason,
                "fastest_lap": car.has_fastest_lap,
            }
            for car in result["results"]
        ]

        return {
            "race_name": race.name,
            "circuit": race.circuit,
            "country": race.country,
            "weather": result["weather"].value if hasattr(result["weather"], "value") else str(result["weather"]),
            "results": formatted_results,
            "events": result["events"],
            "staff_insights": result.get("staff_insights", {}),
        }

    # ── Private sub-methods ──────────────────────────────────────────────────

    async def _save_race_results(self, race, teams: list, league_id: int, result: dict):
        """Save RaceResult rows, update team stats, update standings."""
        for car in result["results"]:
            points = F1_POINTS.get(car.position, 0) if not car.is_dnf else 0

            race_result = RaceResult(
                race_id=race.id,
                team_id=car.team_id,
                driver_id=car.driver_id,
                position=car.position if not car.is_dnf else None,
                points=points,
                fastest_lap=car.has_fastest_lap,
                dnf=car.is_dnf,
                dnf_reason=car.dnf_reason if car.is_dnf else None,
                pit_stops=car.pit_stops_done,
            )
            self.db.add(race_result)

            team = next((t for t in teams if t.id == car.team_id), None)
            if team and not car.is_dnf:
                team.total_points = (team.total_points or 0) + points
                if car.position == 1:
                    team.wins = (team.wins or 0) + 1
                if car.position and car.position <= 3:
                    team.podiums = (team.podiums or 0) + 1

            await self._update_constructor_standing(league_id, race.season, car.team_id, points)
            pos = car.position if not car.is_dnf else None
            await self._update_driver_standing(
                league_id, race.season, car.driver_id, car.team_id, points,
                pos == 1, bool(pos and pos <= 3), car.has_fastest_lap,
            )

    async def _award_prize_money(self, teams: list, result: dict):
        """Pay top-10 finishers their prize money."""
        prizes = [5_000_000, 3_000_000, 2_000_000, 1_500_000, 1_000_000,
                  800_000, 600_000, 400_000, 200_000, 100_000]
        for i, car in enumerate(result["results"][:10]):
            team = next((t for t in teams if t.id == car.team_id), None)
            if team:
                team.budget += prizes[i]

    async def _process_all_sponsors(self, result: dict):
        """Process sponsor contracts for every car in the result."""
        for car in result["results"]:
            await self._process_sponsors(car.team_id, car.position if not car.is_dnf else None)

    async def _check_all_achievements(self, result: dict):
        """Check achievements for every car in the result."""
        weather = result["weather"]
        for car in result["results"]:
            await self._check_achievements(car.team_id, car.position if not car.is_dnf else None, weather)

    async def _generate_staff_insights(self, teams: list, result: dict, league_id: int) -> dict:
        """Generate per-team staff insights for the post-race report."""
        next_race_result = await self.db.execute(
            select(Race).where(
                and_(Race.league_id == league_id, Race.status == RaceStatus.SCHEDULED)
            ).order_by(Race.round.asc()).limit(1)
        )
        next_race = next_race_result.scalar_one_or_none()
        next_circuit = next_race.circuit if next_race else "the next race"

        team_insights = {}
        for team in teams:
            staff_result = await self.db.execute(
                select(TeamStaff, Staff)
                .join(Staff, TeamStaff.staff_id == Staff.id)
                .where(TeamStaff.team_id == team.id)
            )
            team_staff = staff_result.all()
            if team_staff:
                team_stats = {
                    "engine": team.engine, "aerodynamics": team.aerodynamics,
                    "chassis": team.chassis, "reliability": team.reliability,
                    "tyres": team.tyres, "pit_crew": team.pit_crew,
                }
                team_insights[team.id] = generate_staff_race_insights(
                    team_staff, result, team.id, team_stats, next_circuit
                )
        return team_insights


    async def _update_constructor_standing(self, league_id, season, team_id, points):
        result = await self.db.execute(
            select(ConstructorStanding).where(
                and_(ConstructorStanding.league_id == league_id,
                     ConstructorStanding.season == season,
                     ConstructorStanding.team_id == team_id)
            )
        )
        standing = result.scalar_one_or_none()
        if not standing:
            standing = ConstructorStanding(
                league_id=league_id, season=season, team_id=team_id,
                points=0, wins=0, podiums=0
            )
            self.db.add(standing)
            await self.db.flush()
        standing.points = (standing.points or 0) + points
        if points >= 25:
            standing.wins = (standing.wins or 0) + 1
        if points >= 15:
            standing.podiums = (standing.podiums or 0) + 1

    async def _update_driver_standing(self, league_id, season, driver_id, team_id, points,
                                       is_win, is_podium, is_fl):
        result = await self.db.execute(
            select(DriverStanding).where(
                and_(DriverStanding.league_id == league_id,
                     DriverStanding.season == season,
                     DriverStanding.driver_id == driver_id)
            )
        )
        standing = result.scalar_one_or_none()
        if not standing:
            standing = DriverStanding(
                league_id=league_id, season=season,
                driver_id=driver_id, team_id=team_id,
                points=0, wins=0, podiums=0, poles=0, fastest_laps=0
            )
            self.db.add(standing)
            await self.db.flush()
        standing.points = (standing.points or 0) + points
        if is_win:
            standing.wins = (standing.wins or 0) + 1
        if is_podium:
            standing.podiums = (standing.podiums or 0) + 1
        if is_fl:
            standing.fastest_laps = (standing.fastest_laps or 0) + 1

    async def _process_sponsors(self, team_id: int, position: Optional[int]):
        sponsors_result = await self.db.execute(
            select(TeamSponsor, Sponsor)
            .join(Sponsor, TeamSponsor.sponsor_id == Sponsor.id)
            .where(and_(TeamSponsor.team_id == team_id, TeamSponsor.is_active == True))
        )
        team = await TeamService(self.db).get(team_id)

        for ts, sp in sponsors_result.all():
            ts.races_completed += 1
            success = False

            if sp.target_position and position and position <= sp.target_position:
                success = True
            elif not sp.target_position:
                success = True  # Just for completing race

            if success:
                team.budget += sp.reward
                team.reputation = min(100, team.reputation + 1)
                ts.total_earned += sp.reward
            else:
                team.budget -= sp.penalty
                team.reputation = max(0, team.reputation - 1)

            if ts.races_completed >= ts.contract_races:
                ts.is_active = False

    async def _check_achievements(self, team_id: int, position: Optional[int], weather):
        team = await TeamService(self.db).get(team_id)
        if not team:
            return

        async def award(key: str):
            ach_result = await self.db.execute(
                select(Achievement).where(Achievement.key == key)
            )
            ach = ach_result.scalar_one_or_none()
            if not ach:
                return

            existing = await self.db.execute(
                select(TeamAchievement).where(
                    and_(TeamAchievement.team_id == team_id,
                         TeamAchievement.achievement_id == ach.id)
                )
            )
            if existing.scalar_one_or_none():
                return

            ta = TeamAchievement(team_id=team_id, achievement_id=ach.id)
            self.db.add(ta)
            team.budget += ach.reward_money
            team.research_points += ach.reward_rp
            team.reputation = min(100, team.reputation + ach.reward_reputation)

        await award("first_race")
        if position == 1:
            await award("first_win")
        if position and position <= 3:
            await award("first_podium")
        if team.total_points >= 100:
            await award("hundred_points")
        if weather == "heavy_rain" and position == 1:
            await award("rain_master")

    async def _end_season(self, league: League):
        """End season, award champions"""
        # Find constructor champion
        const_result = await self.db.execute(
            select(ConstructorStanding).where(
                and_(ConstructorStanding.league_id == league.id,
                     ConstructorStanding.season == league.current_season)
            ).order_by(ConstructorStanding.points.desc()).limit(1)
        )
        champion_team = const_result.scalar_one_or_none()

        # Find driver champion
        driver_result = await self.db.execute(
            select(DriverStanding).where(
                and_(DriverStanding.league_id == league.id,
                     DriverStanding.season == league.current_season)
            ).order_by(DriverStanding.points.desc()).limit(1)
        )
        champion_driver = driver_result.scalar_one_or_none()

        # Update season record
        season_result = await self.db.execute(
            select(Season).where(
                and_(Season.league_id == league.id,
                     Season.season_number == league.current_season)
            )
        )
        season = season_result.scalar_one_or_none()
        if season:
            season.is_active = False
            season.ended_at = datetime.utcnow()
            if champion_team:
                season.champion_team_id = champion_team.team_id
            if champion_driver:
                season.champion_driver_id = champion_driver.driver_id

        # Award champion team
        if champion_team:
            team = await TeamService(self.db).get(champion_team.team_id)
            if team:
                team.budget += 100_000_000  # Championship prize
                team.reputation = min(100, team.reputation + 20)

        # Start new season
        league.current_season += 1
        league.current_race = 0
        league.status = LeagueStatus.WAITING

        # Age drivers
        all_drivers_result = await self.db.execute(select(Driver))
        for d in all_drivers_result.scalars().all():
            d.age += 1
            # Improve young drivers
            if d.age <= 25 and d.development_potential > 50:
                improvement = int(d.development_potential / 20)
                d.skill = min(99, d.skill + improvement)
                d.pace = min(99, d.pace + improvement)


# ─────────────────────────────────────────────
# RESEARCH SERVICE
# ─────────────────────────────────────────────

class ResearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_research(self, team_id: int, tree: str, node_key: str) -> tuple[bool, str]:
        if tree not in RESEARCH_TREES:
            return False, "Invalid research tree!"

        nodes = RESEARCH_TREES[tree]
        node = next((n for n in nodes if n["node"] == node_key), None)
        if not node:
            return False, "Invalid research node!"

        # Check not already done
        existing = await self.db.execute(
            select(ResearchProject).where(
                and_(ResearchProject.team_id == team_id,
                     ResearchProject.node == node_key,
                     ResearchProject.is_complete == True)
            )
        )
        if existing.scalar_one_or_none():
            return False, "Already researched!"

        team = await TeamService(self.db).get(team_id)
        if not team:
            return False, "Team not found!"

        if team.research_points < node["rp_cost"]:
            return False, f"Need {node['rp_cost']} RP, you have {team.research_points} RP"

        if team.budget < node["money_cost"]:
            return False, f"Need ${node['money_cost']:,}, you have ${team.budget:,}"

        # Deduct costs & apply bonus
        team.research_points -= node["rp_cost"]
        team.budget -= node["money_cost"]

        # Apply stat bonus
        current = getattr(team, node["stat"], 0)
        setattr(team, node["stat"], min(100, current + node["bonus"]))

        project = ResearchProject(
            team_id=team_id,
            tree=tree,
            node=node_key,
            rp_cost=node["rp_cost"],
            money_cost=node["money_cost"],
            stat_bonus=node["bonus"],
            is_complete=True,
            completed_at=datetime.utcnow(),
        )
        self.db.add(project)
        await self.db.flush()

        return True, f"Researched {node['name']}! +{node['bonus']} to {node['stat'].replace('_', ' ').title()}"

    async def get_tree_status(self, team_id: int, tree: str) -> dict:
        if tree not in RESEARCH_TREES:
            return {}

        done_result = await self.db.execute(
            select(ResearchProject.node).where(
                and_(ResearchProject.team_id == team_id,
                     ResearchProject.tree == tree,
                     ResearchProject.is_complete == True)
            )
        )
        done_nodes = set(done_result.scalars().all())

        return {
            "tree": tree,
            "nodes": [
                {**n, "done": n["node"] in done_nodes}
                for n in RESEARCH_TREES[tree]
            ]
        }


# ─────────────────────────────────────────────
# STANDINGS SERVICE
# ─────────────────────────────────────────────

class StandingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_constructor_standings(self, league_id: int) -> list:
        # Get current season for this league
        from src.models.models import League
        league_res = await self.db.execute(select(League).where(League.id == league_id))
        league = league_res.scalar_one_or_none()
        season = league.current_season if league else 1

        result = await self.db.execute(
            select(ConstructorStanding, Team)
            .join(Team, ConstructorStanding.team_id == Team.id)
            .where(
                and_(ConstructorStanding.league_id == league_id,
                     ConstructorStanding.season == season)
            )
            .order_by(ConstructorStanding.points.desc())
        )
        rows = result.all()

        # Fallback: if no season-filtered rows, show all (handles season=0 edge case)
        if not rows:
            result2 = await self.db.execute(
                select(ConstructorStanding, Team)
                .join(Team, ConstructorStanding.team_id == Team.id)
                .where(ConstructorStanding.league_id == league_id)
                .order_by(ConstructorStanding.points.desc())
            )
            rows = result2.all()
        return rows

    async def get_driver_standings(self, league_id: int) -> list:
        from src.models.models import League
        league_res = await self.db.execute(select(League).where(League.id == league_id))
        league = league_res.scalar_one_or_none()
        season = league.current_season if league else 1

        result = await self.db.execute(
            select(DriverStanding, Driver, Team)
            .join(Driver, DriverStanding.driver_id == Driver.id)
            .join(Team, DriverStanding.team_id == Team.id)
            .where(
                and_(DriverStanding.league_id == league_id,
                     DriverStanding.season == season)
            )
            .order_by(DriverStanding.points.desc())
        )
        rows = result.all()

        if not rows:
            result2 = await self.db.execute(
                select(DriverStanding, Driver, Team)
                .join(Driver, DriverStanding.driver_id == Driver.id)
                .join(Team, DriverStanding.team_id == Team.id)
                .where(DriverStanding.league_id == league_id)
                .order_by(DriverStanding.points.desc())
            )
            rows = result2.all()
        return rows


# ─────────────────────────────────────────────
# ADMIN SERVICE
# ─────────────────────────────────────────────

class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_money(self, admin_id: int, target_team_id: int, amount: int) -> str:
        team = await TeamService(self.db).get(target_team_id)
        if not team:
            return "Team not found!"
        team.budget += amount
        log = AdminLog(admin_id=admin_id, action="add_money",
                       target_id=target_team_id, details=f"+${amount:,}")
        self.db.add(log)
        await self.db.flush()
        return f"Added ${amount:,} to team {team.name}"

    async def ban_player(self, admin_id: int, user_id: int, reason: str) -> str:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return "User not found!"
        user.is_banned = True
        user.ban_reason = reason
        log = AdminLog(admin_id=admin_id, action="ban_player",
                       target_id=user_id, details=reason)
        self.db.add(log)
        await self.db.flush()
        return f"User {user.first_name} banned. Reason: {reason}"

    async def unban_player(self, admin_id: int, user_id: int) -> str:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return "User not found!"
        user.is_banned = False
        user.ban_reason = None
        log = AdminLog(admin_id=admin_id, action="unban_player", target_id=user_id)
        self.db.add(log)
        await self.db.flush()
        return f"User {user.first_name} unbanned."

    async def get_all_user_ids(self) -> list[int]:
        """Returns all non-banned user IDs for broadcast"""
        result = await self.db.execute(
            select(User.id).where(User.is_banned == False)
        )
        return [row[0] for row in result.fetchall()]

    async def log_suspicious(self, user_id: int, activity: str, details: str, severity: str = "low"):
        log = SuspiciousActivity(
            user_id=user_id, activity_type=activity, details=details, severity=severity
        )
        self.db.add(log)
        await self.db.flush()


# ─────────────────────────────────────────────
# SEEDER
# ─────────────────────────────────────────────

async def seed_database(db: AsyncSession):
    """Seed initial game data — upserts drivers by name so new additions always appear"""
    logger.info("Seeding database (upsert mode)...")

    # ── Drivers: insert only if name not already in DB ──────────────────
    existing_names_res = await db.execute(select(Driver.name))
    existing_names = {row[0] for row in existing_names_res.fetchall()}

    new_count = 0
    for d in REAL_DRIVERS + FICTIONAL_DRIVERS:
        if d["name"] in existing_names:
            continue  # already seeded, skip
        driver = Driver(
            name=d["name"],
            nationality=d["nationality"],
            age=d["age"],
            number=d.get("number"),
            is_fictional=d.get("is_fictional", False),
            skill=d["skill"],
            racecraft=d["racecraft"],
            pace=d["pace"],
            consistency=d["consistency"],
            wet_weather=d["wet_weather"],
            overtaking=d["overtaking"],
            defence=d["defence"],
            development_potential=d["development_potential"],
            base_salary=d["base_salary"],
        )
        db.add(driver)
        new_count += 1

    # ── Staff: insert only if name not already in DB ─────────────────────
    existing_staff_res = await db.execute(select(Staff.name))
    existing_staff = {row[0] for row in existing_staff_res.fetchall()}
    for s in STAFF_DATABASE:
        if s["name"] not in existing_staff:
            db.add(Staff(**s))

    # ── Sponsors: insert only if name not already in DB ──────────────────
    existing_sponsors_res = await db.execute(select(Sponsor.name))
    existing_sponsors = {row[0] for row in existing_sponsors_res.fetchall()}
    for sp in SPONSORS:
        if sp["name"] not in existing_sponsors:
            db.add(Sponsor(**sp))

    # ── Achievements: insert only if name not already in DB ──────────────
    existing_ach_res = await db.execute(select(Achievement.name))
    existing_ach = {row[0] for row in existing_ach_res.fetchall()}
    for a in ACHIEVEMENTS:
        if a["name"] not in existing_ach:
            db.add(Achievement(**a))

    await db.commit()
    logger.info(f"Database seed complete — {new_count} new drivers added.")
