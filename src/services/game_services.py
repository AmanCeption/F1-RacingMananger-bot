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
    generate_weather, Weather
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

        teams_result = await self.db.execute(
            select(func.count(Team.id)).where(Team.league_id == league_id)
        )
        count = teams_result.scalar()
        if count < 2:
            return False, "Need at least 2 teams to start!"

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
                     Race.status == RaceStatus.SCHEDULED)
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
          
