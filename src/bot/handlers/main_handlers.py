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
    except ValueError:
        await message.answer("❌ Invalid values!")
        return

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        success, msg = await DriverMarketService(db).place_bid(team.id, listing_id, amount)
        await message.answer("✅ " + msg if success else "❌ " + msg)


# ─────────────────────────────────────────────
# LEAGUE COMMANDS
# ─────────────────────────────────────────────

@router.message(Command("leagues"))
@router.message(F.text == "👥 League")
async def cmd_leagues(message: Message):
    await message.answer(
        "👥 <b>League System</b>\n\nCompete in leagues against other managers!",
        reply_markup=league_kb()
    )


@router.message(Command("createleague"))
async def cmd_create_league(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

    await state.set_state(LeagueCreateStates.waiting_name)
    await message.answer("🏆 <b>Create a League</b>\n\nEnter your league name:")


@router.message(LeagueCreateStates.waiting_name)
async def league_create_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3 or len(name) > 40:
        await message.answer("❌ League name must be 3-40 characters!")
        return
    await state.update_data(name=name)
    await state.set_state(LeagueCreateStates.waiting_password)
    await message.answer(
        f"League name: <b>{name}</b>\n\n"
        "Set a password for private access? (or type 'skip' for public league)"
    )


@router.message(LeagueCreateStates.waiting_password)
async def league_create_password(message: Message, state: FSMContext):
    data = await state.get_data()
    password = None if message.text.lower() == "skip" else message.text.strip()
    is_public = password is None

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        try:
            league = await LeagueService(db).create(
                owner_id=message.from_user.id,
                name=data["name"],
                is_public=is_public,
                password=password,
            )
            await state.clear()
            await message.answer(
                f"✅ <b>League Created!</b>\n\n"
                f"🏆 Name: <b>{league.name}</b>\n"
                f"🔑 Invite Code: <code>{league.invite_code}</code>\n"
                f"{'🔒 Private' if password else '🌍 Public'}\n\n"
                f"Share the invite code with friends!\n"
                f"Use /startseason to begin racing when ready."
            )
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()


@router.message(Command("joinleague"))
async def cmd_join_league(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        if team.league_id:
            await message.answer("❌ You're already in a league! Use /leaveleague to leave first.")
            return

    await state.set_state(LeagueJoinStates.waiting_code)
    await message.answer("🔗 Enter the league invite code:")


@router.message(LeagueJoinStates.waiting_code)
async def league_join_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(code=code)

    async with get_session() as db:
        league = await LeagueService(db).get_by_invite(code)
        if not league:
            await message.answer("❌ Invalid invite code!")
            await state.clear()
            return

        if league.password:
            await state.set_state(LeagueJoinStates.waiting_password)
            await message.answer(f"🔒 <b>{league.name}</b> requires a password.\nEnter it:")
        else:
            team = await TeamService(db).get_by_owner(message.from_user.id)
            success, msg = await LeagueService(db).join(team.id, code)
            await state.clear()
            await message.answer("✅ " + msg if success else "❌ " + msg)


@router.message(LeagueJoinStates.waiting_password)
async def league_join_password(message: Message, state: FSMContext):
    data = await state.get_data()
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        success, msg = await LeagueService(db).join(team.id, data["code"], message.text.strip())
        await state.clear()
        await message.answer("✅ " + msg if success else "❌ " + msg)


@router.message(Command("startseason"))
async def cmd_start_season(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ You must be in a league to start a season!")
            return

        success, msg = await LeagueService(db).start_season(team.league_id, message.from_user.id)
        await message.answer("✅ " + msg if success else "❌ " + msg)


# ─────────────────────────────────────────────
# RESEARCH
# ─────────────────────────────────────────────

@router.message(Command("research"))
@router.message(F.text == "🔬 Research")
async def cmd_research(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        await message.answer(
            f"🔬 <b>Research Department</b>\n\n"
            f"Available RP: <b>{team.research_points}</b>\n\n"
            f"Choose a research tree to explore:",
            reply_markup=research_kb(team.id)
        )


@router.callback_query(F.data.startswith("research:tree:"))
async def research_tree(callback: CallbackQuery):
    parts = callback.data.split(":")
    team_id, tree = int(parts[2]), parts[3]

    async with get_session() as db:
        team = await TeamService(db).get(team_id)
        status = await ResearchService(db).get_tree_status(team_id, tree)

        tree_names = {
            "power_unit": "⚡ Power Unit", "aero": "🌬️ Aerodynamics",
            "weight_reduction": "⚖️ Weight Reduction", "reliability": "🔧 Reliability",
            "tyres": "🛞 Tyre Technology"
        }

        text = f"🔬 <b>{tree_names.get(tree, tree)}</b>\n\n"
        text += f"Your RP: <b>{team.research_points}</b>\n\n"

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()

        for node in status["nodes"]:
            if node["done"]:
                text += f"✅ {node['name']} (Done, +{node['stat_bonus']} {node['stat']})\n"
            else:
                text += (
                    f"🔬 {node['name']}\n"
                    f"  Cost: {node['rp_cost']} RP + ${node['money_cost']:,}\n"
                    f"  Bonus: +{node['stat_bonus']} {node['stat'].replace('_', ' ').title()}\n\n"
                )
                builder.button(
                    text=f"Research {node['name']}",
                    callback_data=f"research:do:{team_id}:{tree}:{node['node']}"
                )

        builder.adjust(1)
        builder.row(InlineKeyboardButton(text="◀️ Back", callback_data="research:back"))

        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()


@router.callback_query(F.data.startswith("research:do:"))
async def research_do(callback: CallbackQuery):
    parts = callback.data.split(":")
    team_id, tree, node = int(parts[2]), parts[3], parts[4]

    async with get_session() as db:
        success, msg = await ResearchService(db).start_research(team_id, tree, node)
        await callback.answer("✅ " + msg if success else "❌ " + msg, show_alert=True)
        if success:
            # Refresh tree view
            status = await ResearchService(db).get_tree_status(team_id, tree)
            team = await TeamService(db).get(team_id)
            await callback.message.edit_text(
                f"✅ Research complete!\n\n{msg}\n\nRP remaining: {team.research_points}"
            )


# ─────────────────────────────────────────────
# DAILY REWARD
# ─────────────────────────────────────────────

@router.message(Command("daily"))
@router.message(F.text == "🎁 Daily Reward")
async def cmd_daily(message: Message):
    async with get_session() as db:
        svc = UserService(db)
        result = await svc.claim_daily(message.from_user.id)

        if not result:
            await message.answer("❌ Register first!")
            return

        if not result["available"]:
            await message.answer(
                f"⏳ Daily reward already claimed!\n\n"
                f"Come back in <b>{result['hours']}h {result['minutes']}m</b>"
            )
        else:
            await message.answer(
                f"🎁 <b>Daily Reward Claimed!</b>\n\n"
                f"💰 +${result['money']:,}\n"
                f"🔬 +{result['rp']} Research Points\n\n"
                f"Come back tomorrow for more!"
            )


# ─────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📋 <b>F1 Management Bot — Commands</b>\n\n"
        "<b>Registration:</b>\n"
        "/start — Main menu\n"
        "/register — Create your team\n\n"
        "<b>Team Management:</b>\n"
        "/team — View your team\n"
        "/budget — Budget overview\n"
        "/upgrade — Upgrade car stats\n"
        "/garage — Detailed car info\n\n"
        "<b>Drivers & Staff:</b>\n"
        "/market — Driver transfer market\n"
        "/buydriver <id> — Sign a driver\n"
        "/selldriver <id> [price] — List for transfer\n"
        "/bid <id> <amount> — Bid on auction\n\n"
        "<b>Race Weekend:</b>\n"
        "/practice — Practice session report\n"
        "/strategy — Set race strategy\n"
        "/setup — Adjust car setup\n\n"
        "<b>League:</b>\n"
        "/createleague — Create a league\n"
        "/joinleague — Join with invite code\n"
        "/leaveleague — Leave current league\n"
        "/leagues — Browse public leagues\n"
        "/startseason — Start season (owner)\n\n"
        "<b>Development:</b>\n"
        "/research — Research tree\n"
        "/sponsors — Manage sponsors\n\n"
        "<b>Other:</b>\n"
        "/standings — Championship standings\n"
        "/daily — Claim daily reward\n"
        "/achievements — View achievements\n\n"
        "🏎️ <b>Good luck on track!</b>"
    )
"""
DELETE TEAM HANDLER
Yeh code main_handlers.py mein add karo:

1. States section mein (top par jahan RegisterStates hai):

2. Neeche handlers mein yeh do functions add karo
"""

# ─────────────────────────────────────────────
# DELETE TEAM
# ─────────────────────────────────────────────

@router.message(Command("deleteteam"))
async def cmd_delete_team(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Tumhara koi team nahi hai!")
            return

        await state.set_state(DeleteTeamStates.waiting_confirm)
        await state.update_data(team_id=team.id, team_name=team.name)
        await message.answer(
            f"⚠️ <b>Team Delete Karna Chahte Ho?</b>\n\n"
            f"Team: <b>{safe(team.name)}</b>\n"
            f"Budget: ${team.budget:,}\n\n"
            f"❗ Yeh permanent hai! Sab kuch delete hoga:\n"
            f"Drivers, staff, sponsors, achievements\n\n"
            f"Confirm karne ke liye team ka exact naam type karo:\n"
            f"<code>{safe(team.name)}</code>\n\n"
            f"Cancel karne ke liye /start bhejo"
        )

@router.message(DeleteTeamStates.waiting_confirm)
async def delete_team_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    team_name = data.get("team_name", "")
    team_id = data.get("team_id")

    if message.text.strip() != team_name:
        await message.answer(
            f"❌ Naam match nahi hua!\n\n"
            f"Exactly yeh type karo: <code>{safe(team_name)}</code>\n"
            f"Ya cancel ke liye /start"
        )
        return

    async with get_session() as db:
        from sqlalchemy import delete as sql_delete
        from src.models.models import (
            TeamDriver, TeamStaff, TeamSponsor,
            RaceResult, TeamAchievement, RaceStrategy,
            ConstructorStanding, DriverStanding, ResearchProject
        )

        # Sab related data delete karo
        await db.execute(sql_delete(TeamDriver).where(TeamDriver.team_id == team_id))
        await db.execute(sql_delete(TeamStaff).where(TeamStaff.team_id == team_id))
        await db.execute(sql_delete(TeamSponsor).where(TeamSponsor.team_id == team_id))
        await db.execute(sql_delete(RaceResult).where(RaceResult.team_id == team_id))
        await db.execute(sql_delete(RaceStrategy).where(RaceStrategy.team_id == team_id))
        await db.execute(sql_delete(TeamAchievement).where(TeamAchievement.team_id == team_id))
        await db.execute(sql_delete(ResearchProject).where(ResearchProject.team_id == team_id))
        await db.execute(sql_delete(ConstructorStanding).where(ConstructorStanding.team_id == team_id))

        # Team delete
        from sqlalchemy import select as sql_select
        from src.models.models import Team
        result = await db.execute(sql_select(Team).where(Team.id == team_id))
        team = result.scalar_one_or_none()
        if team:
            # Free agents wapas karo
            for td_result in await db.execute(
                sql_select(TeamDriver).where(TeamDriver.team_id == team_id)
            ):
                pass  # already deleted above
            await db.delete(team)

    await state.clear()
    await message.answer(
        f"✅ <b>Team Delete Ho Gayi!</b>\n\n"
        f"<b>{safe(team_name)}</b> permanently delete ho gayi.\n\n"
        f"Naya team banana chahte ho? /register karo 🏎️"
    )
