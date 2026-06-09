"""
Bot Handlers - Registration, Team, Race, Standings
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.database.session import get_session
from src.services.game_services import (
    UserService, TeamService, LeagueService, RaceService,
    StandingsService, ResearchService, DriverMarketService, seed_database
)
from src.bot.keyboards.keyboards import (
    main_menu_kb, team_menu_kb, upgrade_menu_kb, strategy_kb,
    tyre_selection_kb, market_kb, league_kb, research_kb, pagination_kb
)
from src.core.config import settings, F1_POINTS
from sqlalchemy import select, and_
from src.models.models import Staff, TeamStaff, Team

logger = logging.getLogger(__name__)
router = Router()


def safe(text: str) -> str:
    """Escape HTML special chars"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─────────────────────────────────────────────
# FSM STATES
# ─────────────────────────────────────────────

class RegisterStates(StatesGroup):
    waiting_name = State()
    waiting_logo = State()


class LeagueCreateStates(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_password = State()


class LeagueJoinStates(StatesGroup):
    waiting_code = State()
    waiting_password = State()


class SellDriverStates(StatesGroup):
    waiting_price = State()


class DeleteTeamStates(StatesGroup):
    waiting_confirm = State()


class RenameTeamStates(StatesGroup):
    waiting_newname = State()


# ─────────────────────────────────────────────
# START & REGISTER
# ─────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    async with get_session() as db:
        team_svc = TeamService(db)
        team = await team_svc.get_by_owner(message.from_user.id)

        if team:
            await message.answer(
                f"🏎️ <b>Welcome back, {message.from_user.first_name}!</b>\n\n"
                f"Your team: <b>{team.name}</b>\n"
                f"Budget: <b>${team.budget:,}</b>\n\n"
                "Use the menu below to manage your team!",
                reply_markup=main_menu_kb()
            )
        else:
            await message.answer(
                "🏁 <b>Welcome to F1 Management Bot!</b>\n\n"
                "Build your Formula 1 team, hire drivers, develop your car, "
                "and compete in leagues against other managers!\n\n"
                "📝 Let's create your team. Use /register to begin.\n"
                "Or type /help to see all commands.",
            )


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if team:
            await message.answer("⚠️ You already have a team! Use /team to view it.")
            return

    await state.set_state(RegisterStates.waiting_name)
    await message.answer(
        "🏎️ <b>Team Registration</b>\n\n"
        "What will you name your team?\n"
        "<i>Max 30 characters. No special symbols.</i>"
    )


@router.message(RegisterStates.waiting_name)
async def register_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("❌ Team name too short! Min 3 characters.")
        return
    if len(name) > 30:
        await message.answer("❌ Team name too long! Max 30 characters.")
        return

    await state.update_data(team_name=name)
    await state.set_state(RegisterStates.waiting_logo)
    await message.answer(
        f"✅ Team name: <b>{name}</b>\n\n"
        "📸 Send your team logo URL (optional)\n"
        "Or type <b>skip</b> to use default."
    )


@router.message(RegisterStates.waiting_logo)
async def register_logo(message: Message, state: FSMContext):
    data = await state.get_data()
    logo = None

    if message.text.lower() != "skip":
        url = message.text.strip()
        if url.startswith("http"):
            logo = url

    async with get_session() as db:
        try:
            await seed_database(db)
            team = await TeamService(db).create(
                owner_id=message.from_user.id,
                name=data["team_name"],
                logo_url=logo
            )
            await state.clear()
            await message.answer(
                f"🎉 <b>Team Created!</b>\n\n"
                f"🏎️ Team: <b>{team.name}</b>\n"
                f"💰 Starting Budget: <b>${team.budget:,}</b>\n"
                f"📊 Car Stats: All at 50/100\n\n"
                f"<b>Next steps:</b>\n"
                f"• /market — Sign your drivers\n"
                f"• /createleague or /joinleague — Join competition\n"
                f"• /upgrade — Develop your car\n\n"
                f"Good luck, team principal! 🏆",
                reply_markup=main_menu_kb()
            )
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()


# ─────────────────────────────────────────────
# TEAM COMMANDS
# ─────────────────────────────────────────────

@router.message(Command("team"))
@router.message(F.text == "🏎️ My Team")
async def cmd_team(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ You don't have a team yet! Use /register")
            return

        data = await TeamService(db).get_with_drivers(team.id)
        drivers = data.get("drivers", [])
        staff = data.get("staff", [])
        sponsors = data.get("sponsors", [])

        driver_text = ""
        for d in drivers:
            dr = d["driver"]
            driver_text += f"\n  🏎️ {dr.name} ({dr.nationality}) | Skill: {dr.skill}/100"

        if not driver_text:
            driver_text = "\n  ⚠️ No drivers signed!"

        staff_text = ""
        for s in staff:
            st = s["staff"]
            staff_text += f"\n  👤 {st.name} ({st.role.replace('_', ' ').title()})"

        if not staff_text:
            staff_text = "\n  ⚠️ No staff hired!"

        car_rating = (team.engine + team.aerodynamics + team.chassis +
                      team.reliability + team.tyres + team.pit_crew) // 6

        text = (
            f"🏎️ <b>{team.name}</b>\n"
            f"{'🖼️ ' + team.logo_url if team.logo_url else ''}\n\n"
            f"💰 Budget: <b>${team.budget:,}</b>\n"
            f"⭐ Reputation: <b>{team.reputation}/100</b>\n"
            f"🔬 Research Points: <b>{team.research_points}</b>\n"
            f"🏆 Total Points: <b>{team.total_points}</b>\n"
            f"🥇 Wins: {team.wins} | 🥉 Podiums: {team.podiums}\n\n"
            f"🚗 <b>Car Rating: {car_rating}/100</b>\n"
            f"  ⚙️ Engine: {team.engine} | 🌬️ Aero: {team.aerodynamics}\n"
            f"  🏗️ Chassis: {team.chassis} | 🔧 Reliability: {team.reliability}\n"
            f"  🛞 Tyres: {team.tyres} | 🔩 Pit Crew: {team.pit_crew}\n\n"
            f"<b>Drivers:</b>{driver_text}\n\n"
            f"<b>Staff:</b>{staff_text}\n\n"
            f"<b>Active Sponsors:</b> {len(sponsors)}"
        )

        await message.answer(text, reply_markup=team_menu_kb(team.id))


@router.message(Command("budget"))
async def cmd_budget(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first with /register")
            return

        # Calculate annual expenses
        data = await TeamService(db).get_with_drivers(team.id)
        driver_salaries = sum(d["contract"].salary for d in data["drivers"])
        staff_salaries = sum(s["contract"].salary for s in data["staff"])
        total_expenses = driver_salaries + staff_salaries

        text = (
            f"💰 <b>Budget Report — {team.name}</b>\n\n"
            f"Available: <b>${team.budget:,}</b>\n\n"
            f"📊 <b>Annual Expenses:</b>\n"
            f"  👨‍🏎️ Driver Salaries: ${driver_salaries:,}\n"
            f"  👷 Staff Salaries: ${staff_salaries:,}\n"
            f"  ────────────────\n"
            f"  Total: ${total_expenses:,}\n\n"
            f"💡 Earn more through:\n"
            f"  • Race prizes (up to $5M for win)\n"
            f"  • Sponsor bonuses\n"
            f"  • Championship prize ($100M)\n"
            f"  • /daily reward"
        )
        await message.answer(text)


@router.callback_query(F.data.startswith("upgrade:stat:"))
async def upgrade_stat(callback: CallbackQuery):
    _, _, team_id, stat = callback.data.split(":", 3)
    team_id = int(team_id)

    stat_costs = {
        "engine": 8_000_000, "aerodynamics": 7_000_000, "chassis": 7_000_000,
        "reliability": 5_000_000, "tyres": 4_000_000, "pit_crew": 3_000_000
    }
    stat_labels = {
        "engine": "⚙️ Engine", "aerodynamics": "🌬️ Aerodynamics",
        "chassis": "🏗️ Chassis", "reliability": "🔧 Reliability",
        "tyres": "🛞 Tyres", "pit_crew": "🔩 Pit Crew"
    }

    cost = stat_costs.get(stat, 5_000_000)

    async with get_session() as db:
        try:
            success = await TeamService(db).upgrade_car(team_id, stat, 3, cost)
            if success:
                await callback.message.edit_text(
                    f"✅ <b>Upgrade Complete!</b>\n\n"
                    f"{stat_labels.get(stat, stat)} upgraded by +3!\n"
                    f"Cost: ${cost:,}",
                )
                await callback.answer("✅ Upgraded!")
            else:
                await callback.answer("❌ Insufficient funds!")
        except ValueError as e:
            await callback.answer(f"❌ {e}")


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        text = (
            f"⬆️ <b>Car Development — {team.name}</b>\n\n"
            f"Current Stats:\n"
            f"⚙️ Engine: {team.engine}/100 (upgrade: $8M, +3)\n"
            f"🌬️ Aerodynamics: {team.aerodynamics}/100 (upgrade: $7M, +3)\n"
            f"🏗️ Chassis: {team.chassis}/100 (upgrade: $7M, +3)\n"
            f"🔧 Reliability: {team.reliability}/100 (upgrade: $5M, +3)\n"
            f"🛞 Tyres: {team.tyres}/100 (upgrade: $4M, +3)\n"
            f"🔩 Pit Crew: {team.pit_crew}/100 (upgrade: $3M, +3)\n\n"
            f"💰 Available: ${team.budget:,}\n\n"
            f"<i>Select a stat to upgrade:</i>"
        )
        await message.answer(text, reply_markup=upgrade_menu_kb(team.id))


# ─────────────────────────────────────────────
# RACE COMMANDS
# ─────────────────────────────────────────────

@router.message(Command("strategy"))
@router.message(F.text == "🏁 Race")
async def cmd_strategy(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ Join a league first to access race features!")
            return

        race = await RaceService(db).get_next_race(team.league_id)
        if not race:
            await message.answer("⏳ No upcoming races scheduled yet.")
            return

        data = await TeamService(db).get_with_drivers(team.id)
        if not data["drivers"]:
            await message.answer("❌ You need at least one driver to set a strategy!")
            return

        text = (
            f"🏁 <b>Next Race: {race.name} {race.country}</b>\n"
            f"🏎️ Circuit: {race.circuit}\n"
            f"🔄 Laps: {race.laps}\n\n"
            f"📋 <b>Set Race Strategy</b>\n\n"
            f"Choose strategy for your #1 driver:"
        )
        driver = data["drivers"][0]["driver"]
        await message.answer(
            text,
            reply_markup=strategy_kb(race.id, driver.id)
        )


@router.callback_query(F.data.startswith("strategy:set:"))
async def set_strategy(callback: CallbackQuery):
    parts = callback.data.split(":")
    race_id, driver_id, strategy = int(parts[2]), int(parts[3]), parts[4]

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        await callback.message.edit_text(
            f"✅ Strategy: <b>{strategy.upper()}</b>\n\nNow choose starting tyre:",
            reply_markup=tyre_selection_kb(race_id, driver_id, strategy)
        )
        await callback.answer()


@router.callback_query(F.data.startswith("tyre:set:"))
async def set_tyre(callback: CallbackQuery):
    parts = callback.data.split(":")
    race_id, driver_id, strategy, tyre = int(parts[2]), int(parts[3]), parts[4], parts[5]

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        success, msg = await RaceService(db).set_strategy(team.id, driver_id, race_id, strategy, tyre)
        if success:
            await callback.message.edit_text(
                f"✅ <b>Race Strategy Saved!</b>\n\n"
                f"Strategy: <b>{strategy.upper()}</b>\n"
                f"Starting Tyre: <b>{tyre.title()}</b>\n\n"
                f"Good luck on race day! 🏁"
            )
        else:
            await callback.message.edit_text(f"❌ {msg}")
        await callback.answer()


@router.message(Command("practice"))
async def cmd_practice(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        race = await RaceService(db).get_next_race(team.league_id) if team.league_id else None
        if not race:
            await message.answer("⏳ No upcoming races.")
            return

        from src.simulation.race_engine import generate_practice_report, generate_weather, CarEntry
        from src.simulation.race_engine import Weather

        data = await TeamService(db).get_with_drivers(team.id)
        if not data["drivers"]:
            await message.answer("❌ Sign a driver first!")
            return

        weather = generate_weather()
        driver = data["drivers"][0]["driver"]

        car = CarEntry(
            team_id=team.id, team_name=team.name,
            driver_id=driver.id, driver_name=driver.name,
            pace=driver.pace, racecraft=driver.racecraft,
            consistency=driver.consistency, wet_weather=driver.wet_weather,
            overtaking=driver.overtaking, defence=driver.defence,
            engine=team.engine, aerodynamics=team.aerodynamics,
            chassis=team.chassis, reliability=team.reliability,
            tyre_mgmt=team.tyres, pit_crew=team.pit_crew,
        )

        report = generate_practice_report(car, weather)
        await message.answer(
            f"🔄 <b>Practice Session — {race.name}</b>\n"
            f"Driver: {driver.name}\n\n"
            + report
        )


# ─────────────────────────────────────────────
# STANDINGS
# ─────────────────────────────────────────────

@router.message(Command("standings"))
@router.message(F.text == "🏆 Standings")
async def cmd_standings(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ Join a league to see standings!")
            return

        svc = StandingsService(db)
        constructors = await svc.get_constructor_standings(team.league_id)
        drivers = await svc.get_driver_standings(team.league_id)

        # Constructors
        const_text = "🏗️ <b>Constructors Championship:</b>\n"
        for i, (cs, t) in enumerate(constructors[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            bold_start = "<b>" if t.id == team.id else ""
            bold_end = "</b>" if t.id == team.id else ""
            const_text += f"{medal} {bold_start}{t.name}{bold_end}: {cs.points} pts\n"

        # Drivers
        driver_text = "\n🏎️ <b>Drivers Championship:</b>\n"
        for i, (ds, d, t) in enumerate(drivers[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            driver_text += f"{medal} {d.name} ({t.name}): {ds.points} pts\n"

        await message.answer(const_text + driver_text)


# ─────────────────────────────────────────────
# DRIVER MARKET
# ─────────────────────────────────────────────

@router.message(Command("market"))
@router.message(F.text == "🛒 Driver Market")
async def cmd_market(message: Message):
    await message.answer(
        "🛒 <b>Driver Transfer Market</b>\n\n"
        "Buy and sell drivers, place bids at auctions!",
        reply_markup=market_kb()
    )


@router.callback_query(F.data.startswith("market:free:"))
async def market_free_agents(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    per_page = 5

    async with get_session() as db:
        drivers = await DriverMarketService(db).get_free_agents()

    total_pages = max(1, (len(drivers) + per_page - 1) // per_page)
    page_drivers = drivers[page * per_page:(page + 1) * per_page]

    text = "🆓 <b>Free Agents</b>\n\n"
    for d in page_drivers:
        overall = (d.skill + d.pace + d.racecraft) // 3
        text += (
            f"<b>{d.name}</b> 🇺🇳 {d.nationality} | Age: {d.age}\n"
            f"  ⭐ Overall: {overall} | 💰 Salary: ${d.base_salary:,}/yr\n"
            f"  Use: /buydriver {d.id}\n\n"
        )

    if not page_drivers:
        text += "No free agents available."

    await callback.message.edit_text(
        text,
        reply_markup=pagination_kb("market:free", page, total_pages)
    )
    await callback.answer()


@router.message(Command("buydriver"))
async def cmd_buy_driver(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /buydriver driver_id")
        return

    try:
        driver_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid driver ID!")
        return

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        success, msg = await DriverMarketService(db).buy_driver(team.id, driver_id)
        await message.answer("✅ " + msg if success else "❌ " + msg)


@router.message(Command("selldriver"))
async def cmd_sell_driver(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /selldriver driver_id [price]\n\nAdd 'auction' for auction listing")
        return

    try:
        driver_id = int(parts[1])
        price = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        is_auction = "auction" in message.text.lower()
    except (ValueError, IndexError):
        await message.answer("❌ Invalid format!")
        return

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        success, msg = await DriverMarketService(db).sell_driver(team.id, driver_id, price, is_auction)
        await message.answer("✅ " + msg if success else "❌ " + msg)


@router.message(Command("bid"))
async def cmd_bid(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /bid <listing_id> <amount>")
        return

    try:
        listing_id = int(parts[1])
        amount = int(parts[2])
    except (ValueError, IndexError):
        await message.answer("❌ Invalid format! Use: /bid <listing_id> <amount>")
        return

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        success, msg = await DriverMarketService(db).place_bid(team.id, listing_id, amount)
        await message.answer("✅ " + msg if success else "❌ " + msg)


# ─────────────────────────────────────────────
# ROLE DISPLAY HELPERS
# ─────────────────────────────────────────────

ROLE_EMOJI = {
    "team_principal":       "👔",
    "technical_director":   "🔬",
    "chief_designer":       "📐",
    "head_of_aerodynamics": "💨",
    "aerodynamicist":       "🌬️",
    "chief_race_engineer":  "📻",
    "race_engineer":        "📡",
    "pit_crew_chief":       "🔧",
    "sporting_director":    "📋",
    "power_unit_director":  "⚡",
    "head_of_strategy":     "📊",
    "performance_director": "📈",
}

ROLE_LABEL = {
    "team_principal":       "Team Principal",
    "technical_director":   "Technical Director",
    "chief_designer":       "Chief Designer",
    "head_of_aerodynamics": "Head of Aerodynamics",
    "aerodynamicist":       "Aerodynamicist",
    "chief_race_engineer":  "Chief Race Engineer",
    "race_engineer":        "Race Engineer",
    "pit_crew_chief":       "Pit Crew Chief",
    "sporting_director":    "Sporting Director",
    "power_unit_director":  "Power Unit Director",
    "head_of_strategy":     "Head of Strategy",
    "performance_director": "Performance Director",
}

ROLE_WHAT_THEY_DO = {
    "team_principal":       "Overall leadership & budget management",
    "technical_director":   "Full car performance & development oversight",
    "chief_designer":       "Car design & component architecture",
    "head_of_aerodynamics": "Aero concept & wind tunnel programme",
    "aerodynamicist":       "CFD analysis & aero fine-tuning",
    "chief_race_engineer":  "Race strategy & driver coaching",
    "race_engineer":        "Car setup & in-race adjustments",
    "pit_crew_chief":       "Pit stop speed & crew execution",
    "sporting_director":    "Regulations, protests & logistics",
    "power_unit_director":  "Engine modes, ERS & thermal management",
    "head_of_strategy":     "Pre-race modelling & live strategy calls",
    "performance_director": "Overall performance benchmarking",
}

def _role_str(role) -> str:
    r = role.value if hasattr(role, "value") else str(role)
    return r

def _role_emoji(role) -> str:
    return ROLE_EMOJI.get(_role_str(role), "👤")

def _role_label(role) -> str:
    return ROLE_LABEL.get(_role_str(role), _role_str(role).replace("_", " ").title())


# ─────────────────────────────────────────────
# /staffmarket — Browse available staff
# ─────────────────────────────────────────────

@router.message(Command("staffmarket"))
@router.message(F.text == "👥 Staff Market")
async def cmd_staffmarket(message: Message):
    async with get_session() as db:
        result = await db.execute(
            select(Staff).where(Staff.is_available == True).order_by(Staff.role, Staff.skill.desc())
        )
        all_staff = result.scalars().all()

    if not all_staff:
        await message.answer("❌ No staff available in the market right now.")
        return

    # Group by role
    by_role = {}
    for s in all_staff:
        r = _role_str(s.role)
        by_role.setdefault(r, []).append(s)

    lines = ["👥 <b>STAFF MARKET</b>\n",
             "Use /hirestaff &lt;id&gt; to hire someone.\n"]

    for role_key, members in by_role.items():
        emoji = ROLE_EMOJI.get(role_key, "👤")
        label = ROLE_LABEL.get(role_key, role_key.replace("_"," ").title())
        does = ROLE_WHAT_THEY_DO.get(role_key, "")
        lines.append(f"\n{emoji} <b>{label}</b>")
        lines.append(f"<i>{does}</i>")
        for s in members:
            real_badge = " ⭐" if getattr(s, "is_real", False) else ""
            specialty = f" [{s.specialty}]" if getattr(s, "specialty", None) else ""
            lines.append(
                f"  <code>ID:{s.id}</code> {safe(s.name)}{real_badge}{specialty}\n"
                f"  Skill: {'█' * (s.skill // 10)}{'░' * (10 - s.skill // 10)} {s.skill}/100\n"
                f"  Salary: ${s.salary:,}/season | Bonus: +{round((s.performance_bonus-1)*100,1)}%"
            )

    lines.append("\n⭐ = Real F1 legend")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─────────────────────────────────────────────
# /hirestaff <id> — Hire a staff member
# ─────────────────────────────────────────────

@router.message(Command("hirestaff"))
async def cmd_hirestaff(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /hirestaff &lt;staff_id&gt;\n\nSee /staffmarket for IDs.")
        return

    try:
        staff_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid ID.")
        return

    async with get_session() as db:
        # Get team
        team_result = await db.execute(select(Team).where(Team.owner_id == message.from_user.id))
        team = team_result.scalar_one_or_none()
        if not team:
            await message.answer("❌ You don't have a team! Use /register first.")
            return

        # Get staff
        staff_result = await db.execute(select(Staff).where(Staff.id == staff_id))
        staff = staff_result.scalar_one_or_none()
        if not staff:
            await message.answer("❌ Staff member not found.")
            return
        if not staff.is_available:
            await message.answer("❌ This staff member is not available.")
            return

        # Check budget
        if team.budget < staff.salary:
            await message.answer(
                f"❌ Not enough budget!\n"
                f"Salary: ${staff.salary:,}\n"
                f"Your budget: ${team.budget:,}"
            )
            return

        # Check if already have same role
        existing_result = await db.execute(
            select(TeamStaff).join(Staff, TeamStaff.staff_id == Staff.id)
            .where(and_(TeamStaff.team_id == team.id, Staff.role == staff.role))
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            await message.answer(
                f"❌ You already have a {_role_label(staff.role)}!\n"
                f"Use /firestaff &lt;id&gt; to release them first."
            )
            return

        # Hire
        team.budget -= staff.salary
        staff.is_available = False
        contract = TeamStaff(team_id=team.id, staff_id=staff.id, salary=staff.salary)
        db.add(contract)
        await db.commit()

    real_badge = " ⭐ (F1 Legend)" if getattr(staff, "is_real", False) else ""
    await message.answer(
        f"✅ <b>{safe(staff.name)}</b>{real_badge} hired!\n\n"
        f"{_role_emoji(staff.role)} Role: {_role_label(staff.role)}\n"
        f"⚙️ Skill: {staff.skill}/100\n"
        f"📈 Performance Bonus: +{round((staff.performance_bonus-1)*100,1)}%\n"
        f"💰 Annual Salary: ${staff.salary:,}\n\n"
        f"<i>{ROLE_WHAT_THEY_DO.get(_role_str(staff.role), '')}</i>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /mystaff — View your hired staff
# ─────────────────────────────────────────────

@router.message(Command("mystaff"))
@router.message(F.text == "👥 My Staff")
async def cmd_mystaff(message: Message):
    async with get_session() as db:
        team_result = await db.execute(select(Team).where(Team.owner_id == message.from_user.id))
        team = team_result.scalar_one_or_none()
        if not team:
            await message.answer("❌ You don't have a team! Use /register first.")
            return

        staff_result = await db.execute(
            select(TeamStaff, Staff)
            .join(Staff, TeamStaff.staff_id == Staff.id)
            .where(TeamStaff.team_id == team.id)
        )
        staff_list = staff_result.all()

    if not staff_list:
        await message.answer(
            "👥 <b>Your Staff</b>\n\n"
            "⚠️ No staff hired yet!\n\n"
            "Use /staffmarket to browse available staff.\n"
            "Staff provide performance bonuses and post-race insights.",
            parse_mode="HTML"
        )
        return

    total_salary = sum(ts.salary for ts, s in staff_list)
    total_bonus = 1.0
    for ts, s in staff_list:
        total_bonus *= s.performance_bonus
    total_bonus = min(1.25, total_bonus)

    lines = [f"👥 <b>YOUR STAFF — {safe(team.name)}</b>\n"]

    for ts, s in staff_list:
        real_badge = " ⭐" if getattr(s, "is_real", False) else ""
        specialty = f" [{s.specialty}]" if getattr(s, "specialty", None) else ""
        lines.append(
            f"{_role_emoji(s.role)} <b>{safe(s.name)}</b>{real_badge}\n"
            f"  {_role_label(s.role)}{specialty}\n"
            f"  Skill: {s.skill}/100 | Bonus: +{round((s.performance_bonus-1)*100,1)}%\n"
            f"  Salary: ${ts.salary:,} | ID: {ts.id}\n"
            f"  <i>/firestaff {ts.id} to release</i>"
        )

    lines.append(f"\n💰 Total Staff Wages: ${total_salary:,}/season")
    lines.append(f"📈 Combined Performance Bonus: +{round((total_bonus-1)*100,1)}%")
    lines.append(f"\n💡 Post-race insights unlocked for {len(staff_list)} role(s)")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ─────────────────────────────────────────────
# /firestaff <contract_id> — Release a staff member
# ─────────────────────────────────────────────

@router.message(Command("firestaff"))
async def cmd_firestaff(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /firestaff &lt;contract_id&gt;\n\nSee /mystaff for IDs.")
        return

    try:
        contract_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid ID.")
        return

    async with get_session() as db:
        team_result = await db.execute(select(Team).where(Team.owner_id == message.from_user.id))
        team = team_result.scalar_one_or_none()
        if not team:
            await message.answer("❌ You don't have a team.")
            return

        contract_result = await db.execute(
            select(TeamStaff, Staff)
            .join(Staff, TeamStaff.staff_id == Staff.id)
            .where(and_(TeamStaff.id == contract_id, TeamStaff.team_id == team.id))
        )
        row = contract_result.one_or_none()
        if not row:
            await message.answer("❌ Contract not found or doesn't belong to your team.")
            return

        ts, s = row
        s.is_available = True
        await db.delete(ts)
        await db.commit()

    await message.answer(
        f"🚪 <b>{safe(s.name)}</b> released.\n"
        f"They are now available in the market again.",
        parse_mode="HTML"
    )
