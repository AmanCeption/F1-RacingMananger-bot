"""
Database Models - Full Schema
"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    BigInteger, String, Integer, Float, Boolean, DateTime, Date,
    ForeignKey, Text, JSON, UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class LeagueStatus(str, enum.Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"


class RaceStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    PRACTICE = "practice"
    QUALIFYING = "qualifying"
    RACING = "racing"
    FINISHED = "finished"


class WeatherCondition(str, enum.Enum):
    SUNNY = "sunny"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    MIXED = "mixed"


class TyreCompound(str, enum.Enum):
    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"
    INTERMEDIATE = "intermediate"
    WET = "wet"


class TransferStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class StaffRole(str, enum.Enum):
    TEAM_PRINCIPAL      = "team_principal"
    TECHNICAL_DIRECTOR  = "technical_director"
    HEAD_OF_STRATEGY    = "head_of_strategy"
    CHIEF_RACE_ENGINEER = "chief_race_engineer"
    # Legacy roles kept so existing DB rows don't break
    CHIEF_DESIGNER       = "chief_designer"
    HEAD_OF_AERODYNAMICS = "head_of_aerodynamics"
    AERODYNAMICIST       = "aerodynamicist"
    RACE_ENGINEER        = "race_engineer"
    PIT_CREW_CHIEF       = "pit_crew_chief"
    SPORTING_DIRECTOR    = "sporting_director"
    POWER_UNIT_DIRECTOR  = "power_unit_director"
    PERFORMANCE_DIRECTOR = "performance_director"


# ─────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user ID
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_daily: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    login_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_command_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    command_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    teams: Mapped[List["Team"]] = relationship("Team", back_populates="owner")
    admin_logs: Mapped[List["AdminLog"]] = relationship("AdminLog", back_populates="admin")


# ─────────────────────────────────────────────
# LEAGUE
# ─────────────────────────────────────────────

class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    invite_code: Mapped[str] = mapped_column(String(16), unique=True)
    password: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    group_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram group linked to this league
    status: Mapped[LeagueStatus] = mapped_column(SAEnum(LeagueStatus), default=LeagueStatus.WAITING)
    current_season: Mapped[int] = mapped_column(Integer, default=1)
    current_race: Mapped[int] = mapped_column(Integer, default=0)
    max_teams: Mapped[int] = mapped_column(Integer, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    teams: Mapped[List["Team"]] = relationship("Team", back_populates="league")
    races: Mapped[List["Race"]] = relationship("Race", back_populates="league")
    seasons: Mapped[List["Season"]] = relationship("Season", back_populates="league")


# ─────────────────────────────────────────────
# TEAM
# ─────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    league_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(64))
    logo_url: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    budget: Mapped[int] = mapped_column(BigInteger, default=100_000_000)
    reputation: Mapped[int] = mapped_column(Integer, default=30)  # 0-100
    research_points: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    podiums: Mapped[int] = mapped_column(Integer, default=0)
    poles: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Car attributes (1-100)
    engine: Mapped[int] = mapped_column(Integer, default=50)
    aerodynamics: Mapped[int] = mapped_column(Integer, default=50)
    chassis: Mapped[int] = mapped_column(Integer, default=50)
    reliability: Mapped[int] = mapped_column(Integer, default=50)
    tyres: Mapped[int] = mapped_column(Integer, default=50)
    pit_crew: Mapped[int] = mapped_column(Integer, default=50)

    # Facility levels (1-5)
    factory_level: Mapped[int] = mapped_column(Integer, default=1)
    wind_tunnel_level: Mapped[int] = mapped_column(Integer, default=1)
    simulator_level: Mapped[int] = mapped_column(Integer, default=1)
    hq_level: Mapped[int] = mapped_column(Integer, default=1)

    owner: Mapped["User"] = relationship("User", back_populates="teams")
    league: Mapped[Optional["League"]] = relationship("League", back_populates="teams")
    drivers: Mapped[List["TeamDriver"]] = relationship("TeamDriver", back_populates="team", cascade="all, delete-orphan")
    staff: Mapped[List["TeamStaff"]] = relationship("TeamStaff", back_populates="team", cascade="all, delete-orphan")
    sponsors: Mapped[List["TeamSponsor"]] = relationship("TeamSponsor", back_populates="team", cascade="all, delete-orphan")
    results: Mapped[List["RaceResult"]] = relationship("RaceResult", back_populates="team", cascade="all, delete-orphan")
    achievements: Mapped[List["TeamAchievement"]] = relationship("TeamAchievement", back_populates="team", cascade="all, delete-orphan")
    research_projects: Mapped[List["ResearchProject"]] = relationship("ResearchProject", back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_id", "league_id", name="uq_team_owner_league"),
    )


# ─────────────────────────────────────────────
# DRIVER
# ─────────────────────────────────────────────

class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    nationality: Mapped[str] = mapped_column(String(32))
    age: Mapped[int] = mapped_column(Integer)
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_fictional: Mapped[bool] = mapped_column(Boolean, default=False)

    # Skills (1-100)
    skill: Mapped[int] = mapped_column(Integer, default=70)
    racecraft: Mapped[int] = mapped_column(Integer, default=70)
    pace: Mapped[int] = mapped_column(Integer, default=70)
    consistency: Mapped[int] = mapped_column(Integer, default=70)
    wet_weather: Mapped[int] = mapped_column(Integer, default=70)
    overtaking: Mapped[int] = mapped_column(Integer, default=70)
    defence: Mapped[int] = mapped_column(Integer, default=70)
    development_potential: Mapped[int] = mapped_column(Integer, default=50)  # growth rate

    # Contract
    base_salary: Mapped[int] = mapped_column(BigInteger, default=5_000_000)
    is_free_agent: Mapped[bool] = mapped_column(Boolean, default=True)

    # Career
    career_wins: Mapped[int] = mapped_column(Integer, default=0)
    career_poles: Mapped[int] = mapped_column(Integer, default=0)
    career_points: Mapped[int] = mapped_column(Integer, default=0)

    team_contracts: Mapped[List["TeamDriver"]] = relationship("TeamDriver", back_populates="driver")
    race_results: Mapped[List["RaceResult"]] = relationship("RaceResult", back_populates="driver")
    transfer_listings: Mapped[List["DriverTransfer"]] = relationship("DriverTransfer", back_populates="driver")


class TeamDriver(Base):
    __tablename__ = "team_drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey("drivers.id"))
    salary: Mapped[int] = mapped_column(BigInteger)
    contract_years: Mapped[int] = mapped_column(Integer, default=1)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)  # driver 1 or 2
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    team: Mapped["Team"] = relationship("Team", back_populates="drivers")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="team_contracts")


# ─────────────────────────────────────────────
# STAFF
# ─────────────────────────────────────────────

class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(64))
    nationality: Mapped[str] = mapped_column(String(32))
    skill: Mapped[int] = mapped_column(Integer, default=70)  # 1-100
    salary: Mapped[int] = mapped_column(BigInteger, default=2_000_000)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_real: Mapped[bool] = mapped_column(Boolean, default=False)  # real F1 legend
    specialty: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # e.g. "aero", "strategy", "engine"

    # Role-specific bonus (%)
    performance_bonus: Mapped[float] = mapped_column(Float, default=1.0)

    team_assignments: Mapped[List["TeamStaff"]] = relationship("TeamStaff", back_populates="staff")


class TeamStaff(Base):
    __tablename__ = "team_staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"))
    salary: Mapped[int] = mapped_column(BigInteger)
    hired_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    team: Mapped["Team"] = relationship("Team", back_populates="staff")
    staff: Mapped["Staff"] = relationship("Staff", back_populates="team_assignments")


# ─────────────────────────────────────────────
# RACE
# ─────────────────────────────────────────────

class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True)
    season: Mapped[int] = mapped_column(Integer, default=1)
    round: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(64))
    circuit: Mapped[str] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(8))
    laps: Mapped[int] = mapped_column(Integer)
    status: Mapped[RaceStatus] = mapped_column(SAEnum(RaceStatus), default=RaceStatus.SCHEDULED)
    weather: Mapped[Optional[WeatherCondition]] = mapped_column(SAEnum(WeatherCondition), nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    race_log: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # lap events

    league: Mapped["League"] = relationship("League", back_populates="races")
    results: Mapped[List["RaceResult"]] = relationship("RaceResult", back_populates="race")
    strategies: Mapped[List["RaceStrategy"]] = relationship("RaceStrategy", back_populates="race")
    qualifyings: Mapped[List["QualifyingResult"]] = relationship("QualifyingResult", back_populates="race")


class RaceResult(Base):
    __tablename__ = "race_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"))
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey("drivers.id"))
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    fastest_lap: Mapped[bool] = mapped_column(Boolean, default=False)
    dnf: Mapped[bool] = mapped_column(Boolean, default=False)
    dnf_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pit_stops: Mapped[int] = mapped_column(Integer, default=1)
    tyre_strategy: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="results")
    team: Mapped["Team"] = relationship("Team", back_populates="results")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="race_results")


class QualifyingResult(Base):
    __tablename__ = "qualifying_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"))
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey("drivers.id"))
    grid_position: Mapped[int] = mapped_column(Integer)
    q1_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    q2_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    q3_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="qualifyings")


class RaceStrategy(Base):
    __tablename__ = "race_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"))
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey("drivers.id"))
    strategy_type: Mapped[str] = mapped_column(String(16))  # 1stop/2stop/3stop/aggressive/balanced/conservative
    starting_tyre: Mapped[TyreCompound] = mapped_column(SAEnum(TyreCompound))
    car_setup: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="strategies")


# ─────────────────────────────────────────────
# SEASON & STANDINGS
# ─────────────────────────────────────────────

class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"))
    season_number: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    champion_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    champion_driver_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("drivers.id"), nullable=True)

    league: Mapped["League"] = relationship("League", back_populates="seasons")


class DriverStanding(Base):
    __tablename__ = "driver_standings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"))
    season: Mapped[int] = mapped_column(Integer)
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey("drivers.id"))
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    points: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    podiums: Mapped[int] = mapped_column(Integer, default=0)
    poles: Mapped[int] = mapped_column(Integer, default=0)
    fastest_laps: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("league_id", "season", "driver_id", name="uq_driver_standing"),
    )


class ConstructorStanding(Base):
    __tablename__ = "constructor_standings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"))
    season: Mapped[int] = mapped_column(Integer)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    points: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    podiums: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("league_id", "season", "team_id", name="uq_constructor_standing"),
    )


# ─────────────────────────────────────────────
# DRIVER MARKET
# ─────────────────────────────────────────────

class DriverTransfer(Base):
    __tablename__ = "driver_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(Integer, ForeignKey("drivers.id"))
    selling_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    buying_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    asking_price: Mapped[int] = mapped_column(BigInteger)
    final_price: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    is_auction: Mapped[bool] = mapped_column(Boolean, default=False)
    auction_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    highest_bid: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    highest_bidder_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[TransferStatus] = mapped_column(SAEnum(TransferStatus), default=TransferStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    driver: Mapped["Driver"] = relationship("Driver", back_populates="transfer_listings")


# ─────────────────────────────────────────────
# SPONSORS
# ─────────────────────────────────────────────

class Sponsor(Base):
    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    tier: Mapped[str] = mapped_column(String(16))  # small/medium/premium/title
    reward: Mapped[int] = mapped_column(BigInteger)
    target_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # finish requirement
    target_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    penalty: Mapped[int] = mapped_column(BigInteger, default=0)
    min_reputation: Mapped[int] = mapped_column(Integer, default=0)

    team_sponsors: Mapped[List["TeamSponsor"]] = relationship("TeamSponsor", back_populates="sponsor")


class TeamSponsor(Base):
    __tablename__ = "team_sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    sponsor_id: Mapped[int] = mapped_column(Integer, ForeignKey("sponsors.id"))
    contract_races: Mapped[int] = mapped_column(Integer, default=5)
    races_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_earned: Mapped[int] = mapped_column(BigInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    terminated_by: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # "team", "sponsor", "expired"
    termination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    team: Mapped["Team"] = relationship("Team", back_populates="sponsors")
    sponsor: Mapped["Sponsor"] = relationship("Sponsor", back_populates="team_sponsors")


# ─────────────────────────────────────────────
# RESEARCH
# ─────────────────────────────────────────────

class ResearchProject(Base):
    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    tree: Mapped[str] = mapped_column(String(32))  # power_unit/aero/weight/reliability/tyres
    node: Mapped[str] = mapped_column(String(64))
    rp_cost: Mapped[int] = mapped_column(Integer)
    money_cost: Mapped[int] = mapped_column(BigInteger)
    stat_bonus: Mapped[int] = mapped_column(Integer)  # +N to affected stat
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    team: Mapped["Team"] = relationship("Team", back_populates="research_projects")


# ─────────────────────────────────────────────
# ACHIEVEMENTS
# ─────────────────────────────────────────────

class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(8), default="🏆")
    reward_money: Mapped[int] = mapped_column(BigInteger, default=0)
    reward_rp: Mapped[int] = mapped_column(Integer, default=0)
    reward_reputation: Mapped[int] = mapped_column(Integer, default=0)


class TeamAchievement(Base):
    __tablename__ = "team_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    achievement_id: Mapped[int] = mapped_column(Integer, ForeignKey("achievements.id"))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    team: Mapped["Team"] = relationship("Team", back_populates="achievements")
    achievement: Mapped["Achievement"] = relationship("Achievement")


# ─────────────────────────────────────────────
# ADMIN LOG
# ─────────────────────────────────────────────

class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    admin: Mapped["User"] = relationship("User", back_populates="admin_logs")


# ─────────────────────────────────────────────
# ANTI-CHEAT LOG
# ─────────────────────────────────────────────

class SuspiciousActivity(Base):
    __tablename__ = "suspicious_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    activity_type: Mapped[str] = mapped_column(String(64))
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="low")  # low/medium/high
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
