"""
Bot Handlers - Registration, Team, Race, Standings
"""
import logging
import asyncio
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.database.session import get_session
from src.services.game_services import (
    UserService, TeamService, LeagueService, RaceService,
    StandingsService, ResearchService, DriverMarketService, SponsorService, seed_database
)
from src.bot.keyboards.keyboards import (
    main_menu_kb, team_menu_kb, upgrade_menu_kb, strategy_kb,
    tyre_selection_kb, market_kb, league_kb, research_kb, pagination_kb,
    sponsors_kb, sponsor_sign_kb, sponsor_terminate_kb
)
from src.core.config import settings, F1_POINTS
from sqlalchemy import select, and_
from src.models.models import Staff, TeamStaff, Team, Sponsor, TeamSponsor
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()


def _fmt_pole(pole: dict) -> str:
    """Format pole lap time from grid entry."""
    t = pole.get("q3") or pole.get("q2") or pole.get("q1")
    if t is None:
        return "—"
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:06.3f}"


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


class DeleteLeagueStates(StatesGroup):
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
            # Global name uniqueness check
            from sqlalchemy import select as sa_select, func as sa_func
            from src.models.models import Team as TeamModel
            dup = await db.execute(
                sa_select(TeamModel).where(
                    sa_func.lower(TeamModel.name) == data["team_name"].lower().strip()
                )
            )
            if dup.scalar_one_or_none():
                await state.set_state(RegisterStates.waiting_name)
                await message.answer("❌ That team name is already taken! Please send a different name:")
                return
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
            dev_stars = "🌟" * (dr.development_potential // 25) if dr.age <= 25 else ""
            growth_tag = f" <i>(🌱 Potential: {dr.development_potential}%)</i>" if dr.age <= 25 and dr.development_potential > 50 else ""
            driver_text += (
                f"\n  🏎️ {dr.name} ({dr.nationality}, Age {dr.age}){dev_stars}\n"
                f"     Skill: {dr.skill} | Pace: {dr.pace} | Consistency: {dr.consistency}{growth_tag}"
            )

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
                # Re-fetch team to show updated stats
                team = await TeamService(db).get(team_id)
                new_val = getattr(team, stat, 0) if team else 0
                car_rating = (team.engine + team.aerodynamics + team.chassis +
                              team.reliability + team.tyres + team.pit_crew) // 6 if team else 0
                await callback.message.edit_text(
                    f"✅ <b>Upgrade Complete!</b>\n\n"
                    f"{stat_labels.get(stat, stat)}: <b>{new_val - 3} → {new_val}/100</b> (+3)\n"
                    f"💸 Cost: <b>${cost:,}</b>\n"
                    f"💰 Remaining Budget: <b>${team.budget:,}</b>\n\n"
                    f"🚗 <b>Updated Car Stats:</b>\n"
                    f"  ⚙️ Engine: {team.engine} | 🌬️ Aero: {team.aerodynamics}\n"
                    f"  🏗️ Chassis: {team.chassis} | 🔧 Reliability: {team.reliability}\n"
                    f"  🛞 Tyres: {team.tyres} | 🔩 Pit Crew: {team.pit_crew}\n"
                    f"  📊 Overall Rating: <b>{car_rating}/100</b>\n\n"
                    f"<i>Use /upgrade to continue developing your car.</i>",
                    reply_markup=upgrade_menu_kb(team_id),
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

        driver = data["drivers"][0]["driver"]

        # ── Head of Strategy tyre recommendation ──────────────────────────
        from src.models.models import TeamStaff as TS2, Staff as S2
        from src.core.config import CIRCUIT_DNA, TYRE_DATA
        strat_staff_res = await db.execute(
            select(TS2, S2).join(S2, TS2.staff_id == S2.id)
            .where(and_(TS2.team_id == team.id, S2.role == "head_of_strategy"))
        )
        strat_row = strat_staff_res.first()
        rec_block = ""
        if strat_row:
            hos = strat_row[1]
            dna = CIRCUIT_DNA.get(race.name, {})
            tyre_stress = dna.get("tyre_stress", 1.0)
            overtaking  = dna.get("overtaking_mod", 1.0)
            weather_str = str(race.weather or "sunny").lower()
            # Recommend compound based on circuit traits + weather
            if weather_str in ("heavy_rain", "light_rain"):
                rec_compound = "Intermediate 🟢" if weather_str == "light_rain" else "Wet 🔵"
                rec_strategy = "1-stop"
                reason = "Rain forecast — wet tyres essential"
            elif tyre_stress >= 1.2:
                rec_compound = "Hard ⚪"
                rec_strategy = "1-stop"
                reason = f"High tyre stress circuit ({race.circuit})"
            elif tyre_stress <= 0.85:
                rec_compound = "Soft 🔴"
                rec_strategy = "2-stop"
                reason = f"Low wear circuit — push on softs"
            elif overtaking <= 0.7:
                rec_compound = "Soft 🔴"
                rec_strategy = "1-stop"
                reason = "Overtaking very hard — qualify up front, stay out"
            else:
                rec_compound = "Medium 🟡"
                rec_strategy = "2-stop"
                reason = "Balanced circuit — medium opens both windows"
            skill_tag = f" (Skill {hos.skill}/100)" if hos.skill >= 90 else ""
            rec_block = (
                f"\n\n📊 <b>{hos.name} recommends:</b>{skill_tag}\n"
                f"  🛞 Start on <b>{rec_compound}</b>\n"
                f"  🔁 Strategy: <b>{rec_strategy}</b>\n"
                f"  <i>Reason: {reason}</i>"
            )

        caption = (
            f"🏁 <b>Next Race: {race.name} {race.country}</b>\n"
            f"🏎️ Circuit: {race.circuit}\n"
            f"🔄 Laps: {race.laps}\n"
            f"{rec_block}\n\n"
            f"📋 <b>Set Race Strategy</b>\n\n"
            f"Choose strategy for your #1 driver:"
        )

        # Try sending circuit card as photo with strategy buttons as caption
        try:
            from src.services.circuit_images import generate_circuit_card
            from aiogram.types import BufferedInputFile
            circ_bytes = generate_circuit_card(
                race_name=race.name,
                round_num=race.round,
                weather=race.weather or "",
            )
            await message.answer_photo(
                BufferedInputFile(circ_bytes, filename="circuit.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=strategy_kb(race.id, driver.id),
            )
        except Exception as e:
            logger.warning(f"Circuit card in strategy failed: {e}")
            # Fallback: text only
            await message.answer(
                caption,
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

        new_text = f"✅ Strategy: <b>{strategy.upper()}</b>\n\nNow choose starting tyre:"
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=new_text,
                    parse_mode="HTML",
                    reply_markup=tyre_selection_kb(race_id, driver_id, strategy)
                )
            else:
                await callback.message.edit_text(
                    new_text,
                    reply_markup=tyre_selection_kb(race_id, driver_id, strategy)
                )
        except Exception:
            await callback.message.answer(new_text, reply_markup=tyre_selection_kb(race_id, driver_id, strategy))
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
        saved_text = (
            f"✅ <b>Race Strategy Saved!</b>\n\n"
            f"Strategy: <b>{strategy.upper()}</b>\n"
            f"Starting Tyre: <b>{tyre.title()}</b>\n\n"
            f"Good luck on race day! 🏁"
        ) if success else f"❌ {msg}"
        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=saved_text, parse_mode="HTML")
            else:
                await callback.message.edit_text(saved_text)
        except Exception:
            await callback.message.answer(saved_text)
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

        from src.models.models import RaceStatus
        if race.status == RaceStatus.QUALIFYING:
            await message.answer(
                f"✅ <b>Qualifying already done</b> for <b>{race.name}</b>!\n\n"
                f"🚦 Use /runrace to start the race."
            )
            return
        if race.status in (RaceStatus.RACING, RaceStatus.FINISHED):
            await message.answer(
                f"✅ <b>{race.name}</b> is already completed!\n\n"
                f"🏆 Use /standings to see results."
            )
            return

        from src.simulation.race_engine import generate_practice_report, generate_weather, CarEntry
        from src.simulation.race_engine import Weather
        from src.models.models import TeamStaff, Staff
        from sqlalchemy import select as sa_select2

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

        # Fetch hired staff for pre-race inputs
        staff_result = await db.execute(
            sa_select2(TeamStaff, Staff)
            .join(Staff, TeamStaff.staff_id == Staff.id)
            .where(TeamStaff.team_id == team.id)
        )
        staff_list = staff_result.all()

        report = generate_practice_report(
            car, weather,
            race_name=race.name,
            circuit_name=race.circuit,
            staff_list=staff_list if staff_list else None,
        )

        no_staff_tip = (
            "\n\n💼 <b>Tip:</b> You have no staff hired! Use /staff to sign a Technical Director, "
            "Race Engineer, Head of Strategy and more — they give you circuit-specific pre-race "
            "insights and strategy recommendations every weekend."
            if not staff_list else ""
        )

        await message.answer(
            f"🔄 <b>Practice Session — {race.name}</b>\n"
            f"Circuit: {race.circuit}  {race.country}\n"
            f"Driver: {driver.name}\n\n"
            + report
            + no_staff_tip
            + f"\n\n💡 <b>Next step:</b> /qualifying — Run Q1/Q2/Q3 to set the grid!"
        )


# ─────────────────────────────────────────────
# /qualifying — Full Q1/Q2/Q3 session
# ─────────────────────────────────────────────

@router.message(Command("qualifying"))
@router.message(F.text == "🏎️ Qualifying")
async def cmd_qualifying(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ You must be in a league to run qualifying!")
            return

        from src.models.models import League, LeagueStatus as LS
        from sqlalchemy import select as sa_select
        league_res = await db.execute(sa_select(League).where(League.id == team.league_id))
        league = league_res.scalar_one_or_none()
        if not league or league.owner_id != message.from_user.id:
            await message.answer("❌ Only the league owner can run qualifying!")
            return

        await message.answer("⏱️ Running Q1/Q2/Q3 qualifying session... please wait.")
        try:
            result = await RaceService(db).run_qualifying(team.league_id)
            await db.commit()
        except ValueError as e:
            err = str(e)
            if err.startswith("ALREADY_QUALIFIED:"):
                race_name = err.split(":", 1)[1]
                await message.answer(
                    f"✅ <b>Qualifying already completed</b> for <b>{safe(race_name)}</b>!\n\n"
                    f"🚦 Grid is already set. Use /runrace to start the race."
                )
            elif err.startswith("ALREADY_FINISHED:"):
                race_name = err.split(":", 1)[1]
                await message.answer(
                    f"🏁 <b>{safe(race_name)}</b> is already finished!\n\n"
                    f"🏆 Use /standings to see the results."
                )
            else:
                await message.answer(f"❌ Qualifying error: {err}")
            return
        result = result  # reassign for clarity

    if not result:
        await message.answer("❌ No upcoming race found, or season not started!")
        return

    weather_emoji = {
        "sunny": "☀️", "cloudy": "🌥️", "light_rain": "🌧️",
        "heavy_rain": "⛈️", "mixed": "🌦️"
    }
    w = result.get("weather", "sunny")

    # Send narrative events first (Q1/Q2/Q3 lap times)
    events = result.get("events", [])
    if events:
        events_text = "\n".join(events)
        if len(events_text) > 3800:
            events_text = events_text[:3800] + "\n..."
        await message.answer(events_text)

    # Generate and send qualifying image card
    try:
        from src.services.qualifying_image import generate_qualifying_image
        from aiogram.types import BufferedInputFile

        weather_emojis = {
            "sunny": "☀️", "cloudy": "🌥️", "light_rain": "🌧️",
            "heavy_rain": "⛈️", "mixed": "🌦️",
        }
        weather_label = weather_emojis.get(result.get("weather", ""), "🌤️")
        country = result.get("country", "")

        img_bytes = generate_qualifying_image(
            race_name=result.get("race_name", "Qualifying"),
            circuit=f"{result.get('circuit', '')} {country}",
            weather_label=weather_label,
            grid=result.get("grid", []),
        )
        pole = result.get("grid", [{}])[0]
        caption = (
            f"🏁 <b>Qualifying Complete — {safe(result.get('race_name', ''))}</b>\n\n"
            f"🥇 <b>Pole Position:</b> {safe(pole.get('driver', ''))} ({safe(pole.get('team', ''))})\n"
            f"⏱ <b>Pole Time:</b> {_fmt_pole(pole)}\n\n"
            f"🚦 Race starts next! Use /runrace to begin."
        )
        await message.answer_photo(
            BufferedInputFile(img_bytes, filename="qualifying.png"),
            caption=caption,
            parse_mode="HTML",
        )
    except Exception as e:
        # Fallback to text if image generation fails
        grid_text = f"\n🏁 <b>STARTING GRID — {safe(result['race_name'])}</b>\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for entry in result.get("grid", [])[:20]:
            pos = entry["position"]
            pos_str = medals[pos - 1] if pos <= 3 else f"P{pos:>2}"
            best = entry.get("best_time")
            time_str = ""
            if best:
                m, s = divmod(best, 60)
                time_str = f"  {int(m)}:{s:06.3f}"
            grid_text += f"{pos_str}  {safe(entry['driver'])} <i>({safe(entry['team'])})</i>{time_str}\n"
        grid_text += f"\n🚦 <b>Race starts next!</b> Use /runrace to begin."
        await message.answer(grid_text)

    # Circuit info card after qualifying
    try:
        from src.services.circuit_images import generate_circuit_card
        from aiogram.types import BufferedInputFile
        circ_bytes = generate_circuit_card(
            race_name=result.get("race_name", ""),
            weather=result.get("weather", ""),
        )
        await message.answer_photo(
            BufferedInputFile(circ_bytes, filename="circuit.png"),
            caption=f"🗺️ <b>{safe(result.get('circuit', ''))} {result.get('country','')}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Circuit card failed: {e}")


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


@router.callback_query(F.data.startswith("market:transfers:"))
async def market_transfers(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    per_page = 5

    async with get_session() as db:
        listings = await DriverMarketService(db).get_transfer_listings()

    # Filter fixed-price listings (not auctions)
    fixed = [(t, d, tm) for t, d, tm in listings if not t.is_auction]

    total_pages = max(1, (len(fixed) + per_page - 1) // per_page)
    page_items = fixed[page * per_page:(page + 1) * per_page]

    text = "💸 <b>Transfer List</b>\n\n"
    if page_items:
        for transfer, driver, selling_team in page_items:
            overall = (driver.skill + driver.pace + driver.racecraft) // 3
            seller = selling_team.name if selling_team else "Free Agent"
            text += (
                f"<b>{driver.name}</b> | ⭐ Overall: {overall}\n"
                f"  🏎️ From: {seller}\n"
                f"  💰 Price: <b>${transfer.asking_price:,}</b>\n"
                f"  Use: /buydriver {driver.id}\n\n"
            )
    else:
        text += "No drivers on the transfer list right now.\n\nCheck back after the next race weekend!"

    await callback.message.edit_text(
        text,
        reply_markup=pagination_kb("market:transfers", page, total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("market:auctions:"))
async def market_auctions(callback: CallbackQuery):
    from datetime import datetime as dt
    page = int(callback.data.split(":")[2])
    per_page = 5

    async with get_session() as db:
        listings = await DriverMarketService(db).get_transfer_listings()

    # Filter auction listings only
    auctions = [(t, d, tm) for t, d, tm in listings if t.is_auction]

    total_pages = max(1, (len(auctions) + per_page - 1) // per_page)
    page_items = auctions[page * per_page:(page + 1) * per_page]

    text = "🔨 <b>Live Auctions</b>\n\n"
    if page_items:
        for transfer, driver, selling_team in page_items:
            overall = (driver.skill + driver.pace + driver.racecraft) // 3
            seller = selling_team.name if selling_team else "Free Agent"
            current_bid = transfer.highest_bid or transfer.asking_price
            # Time remaining
            time_left = ""
            if transfer.auction_end:
                remaining = transfer.auction_end - dt.utcnow()
                if remaining.total_seconds() > 0:
                    hrs = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    time_left = f"⏰ {hrs}h {mins}m left"
                else:
                    time_left = "⌛ Expired"

            text += (
                f"<b>{driver.name}</b> | ⭐ Overall: {overall}\n"
                f"  🏎️ From: {seller}\n"
                f"  💰 Current Bid: <b>${current_bid:,}</b>\n"
                f"  {time_left}\n"
                f"  Bid: /bid {transfer.id} &lt;amount&gt;\n\n"
            )
    else:
        text += "No active auctions right now.\n\nSell your driver as an auction with:\n/selldriver &lt;driver_id&gt; auction"

    await callback.message.edit_text(
        text,
        reply_markup=pagination_kb("market:auctions", page, total_pages)
    )
    await callback.answer()


@router.callback_query(F.data == "market:sell")
async def market_sell_menu(callback: CallbackQuery):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!", show_alert=True)
            return

        team_data = await TeamService(db).get_with_drivers(team.id)

    drivers = team_data.get("drivers", [])

    if not drivers:
        await callback.answer("❌ You have no drivers to sell!", show_alert=True)
        return

    text = "📤 <b>Sell a Driver</b>\n\n"
    text += "Your current drivers:\n\n"
    for entry in drivers:
        d = entry["driver"]
        c = entry["contract"]
        overall = (d.skill + d.pace + d.racecraft) // 3
        text += (
            f"<b>{d.name}</b> (ID: {d.id})\n"
            f"  ⭐ Overall: {overall} | 💸 Salary: ${c.salary:,}/yr\n\n"
        )

    text += (
        "To list at fixed price:\n"
        "<code>/selldriver &lt;driver_id&gt; &lt;price&gt;</code>\n\n"
        "To list as auction (24h):\n"
        "<code>/selldriver &lt;driver_id&gt; auction</code>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Back to Market", callback_data="market:free:0"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.message(Command("driver"))
async def cmd_driver_card(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /driver <driver_id>\n\nFind IDs via /market → Free Agents or Transfer List.")
        return

    try:
        driver_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid driver ID!")
        return

    async with get_session() as db:
        from src.models.models import Driver as DriverModel, TeamDriver, Team
        driver_res = await db.execute(
            select(DriverModel).where(DriverModel.id == driver_id)
        )
        driver = driver_res.scalar_one_or_none()
        if not driver:
            await message.answer("❌ Driver not found! Check the ID.")
            return

        # Find current team if contracted
        current_team = None
        if not driver.is_free_agent:
            team_res = await db.execute(
                select(Team)
                .join(TeamDriver, TeamDriver.team_id == Team.id)
                .where(TeamDriver.driver_id == driver_id)
            )
            team_obj = team_res.scalar_one_or_none()
            current_team = team_obj.name if team_obj else None

    from src.services.driver_card import generate_driver_card
    from aiogram.types import BufferedInputFile

    try:
        img_bytes = generate_driver_card(
            name=driver.name,
            nationality=driver.nationality,
            age=driver.age,
            number=driver.number,
            is_fictional=driver.is_fictional,
            skill=driver.skill,
            racecraft=driver.racecraft,
            pace=driver.pace,
            consistency=driver.consistency,
            wet_weather=driver.wet_weather,
            overtaking=driver.overtaking,
            defence=driver.defence,
            development_potential=driver.development_potential,
            base_salary=driver.base_salary,
            is_free_agent=driver.is_free_agent,
            current_team=current_team,
        )
        photo = BufferedInputFile(img_bytes, filename=f"driver_{driver_id}.png")
        status = "🟢 Free Agent" if driver.is_free_agent else f"🔴 Signed ({current_team or 'Unknown'})"
        await message.answer_photo(
            photo,
            caption=f"<b>{driver.name}</b> | {status}\nUse /buydriver {driver_id} to sign.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Driver card generation failed: {e}")
        await message.answer("❌ Couldn't generate driver card. Try again!")


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

        # Capture previous highest bidder for outbid notification
        from src.models.models import DriverTransfer as DT
        from sqlalchemy import select as sa_sel
        prev_res = await db.execute(sa_sel(DT).where(DT.id == listing_id))
        prev_transfer = prev_res.scalar_one_or_none()
        prev_bidder_id = prev_transfer.highest_bidder_id if prev_transfer else None

        success, msg = await DriverMarketService(db).place_bid(team.id, listing_id, amount)
        await message.answer("✅ " + msg if success else "❌ " + msg)

        if success:
            from src.services.notification_service import send_transfer_alert, send_outbid_alert
            await send_transfer_alert(message.bot, db, listing_id, team.name, amount)
            if prev_bidder_id and prev_bidder_id != team.id:
                await send_outbid_alert(message.bot, db, listing_id, prev_bidder_id, amount)


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
# ─────────────────────────────────────────────
# /staffmarket — Browse staff by position (inline buttons)
# ─────────────────────────────────────────────

# 4 main positions shown as buttons
MAIN_POSITIONS = [
    ("team_principal",      "👔 Team Principal"),
    ("technical_director",  "🔬 Technical Director"),
    ("head_of_strategy",    "📊 Head of Strategy"),
    ("chief_race_engineer", "📻 Chief Race Engineer"),
]

POSITION_DETAILS = {
    "team_principal": {
        "emoji": "👔", "label": "Team Principal",
        "what": "Runs the whole team — budget decisions, driver signings, press conferences.",
        "race_effect": "Boosts overall team reputation & budget earnings each race.",
        "stat_boost": "Reputation +20% | Prize money multiplier",
    },
    "technical_director": {
        "emoji": "🔬", "label": "Technical Director",
        "what": "Leads all car development — aerodynamics, chassis, reliability.",
        "race_effect": "Engine, Aero & Chassis upgrades cost less and give bigger gains.",
        "stat_boost": "Car development efficiency +15%",
    },
    "head_of_strategy": {
        "emoji": "📊", "label": "Head of Strategy",
        "what": "Models race strategies before the weekend, calls the pit window live.",
        "race_effect": "Gives tyre compound recommendation + optimal strategy before every race.",
        "stat_boost": "Strategy decisions accuracy +20%",
    },
    "chief_race_engineer": {
        "emoji": "📻", "label": "Chief Race Engineer",
        "what": "On the pit wall — sets up the car & guides the driver through the race.",
        "race_effect": "Post-race telemetry debrief + setup advice before qualifying.",
        "stat_boost": "Lap time improvement +0.1-0.3s per race",
    },
}


def staffmarket_main_kb() -> InlineKeyboardMarkup:
    """4 position buttons + hired staff check."""
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"sm:pos:{role}")]
        for role, label in MAIN_POSITIONS
    ]
    buttons.append([InlineKeyboardButton(text="👥 My Hired Staff", callback_data="sm:mystaff")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def staffmarket_pos_kb(role: str, page: int = 0) -> InlineKeyboardMarkup:
    """Back button + hire buttons per staff entry."""
    buttons = [
        [InlineKeyboardButton(text="⬅️ Back to Positions", callback_data="sm:back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("staffmarket"))
@router.message(F.text == "👥 Staff Market")
async def cmd_staffmarket(message: Message):
    text = (
        "👥 <b>STAFF MARKET</b>\n\n"
        "Hire key personnel to boost your team's performance.\n\n"
        "<b>4 Main Positions Available:</b>\n\n"
        "👔 <b>Team Principal</b> — Overall leadership & prize money boost\n"
        "🔬 <b>Technical Director</b> — Car development & upgrades\n"
        "📊 <b>Head of Strategy</b> — Race strategy & tyre recommendations\n"
        "📻 <b>Chief Race Engineer</b> — Setup advice & race debrief\n\n"
        "<i>Tap a position to see available staff:</i>"
    )
    await message.answer(text, reply_markup=staffmarket_main_kb())


@router.callback_query(F.data == "sm:back")
async def cb_sm_back(callback: CallbackQuery):
    text = (
        "👥 <b>STAFF MARKET</b>\n\n"
        "Hire key personnel to boost your team's performance.\n\n"
        "<b>4 Main Positions Available:</b>\n\n"
        "👔 <b>Team Principal</b> — Overall leadership & prize money boost\n"
        "🔬 <b>Technical Director</b> — Car development & upgrades\n"
        "📊 <b>Head of Strategy</b> — Race strategy & tyre recommendations\n"
        "📻 <b>Chief Race Engineer</b> — Setup advice & race debrief\n\n"
        "<i>Tap a position to see available staff:</i>"
    )
    await callback.message.edit_text(text, reply_markup=staffmarket_main_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("sm:pos:"))
async def cb_sm_position(callback: CallbackQuery):
    role = callback.data.split(":", 2)[2]
    info = POSITION_DETAILS.get(role, {})
    emoji = info.get("emoji", "👤")
    label = info.get("label", role)

    async with get_session() as db:
        result = await db.execute(
            select(Staff)
            .where(and_(Staff.role == role, Staff.is_available == True))
            .order_by(Staff.skill.desc())
        )
        staff_list = result.scalars().all()

        # Check if user already hired this role
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        already_hired = None
        if team:
            hired_res = await db.execute(
                select(Staff.name)
                .join(TeamStaff, TeamStaff.staff_id == Staff.id)
                .where(and_(TeamStaff.team_id == team.id, Staff.role == role))
            )
            already_hired = hired_res.scalar_one_or_none()

    lines = [
        f"{emoji} <b>{label}</b>\n",
        f"📌 <i>{info.get('what', '')}</i>\n",
        f"🏁 <b>Race Effect:</b> {info.get('race_effect', '')}\n",
        f"📈 <b>Stat Boost:</b> {info.get('stat_boost', '')}\n",
    ]

    if already_hired:
        lines.append(f"\n✅ <b>You have hired:</b> {already_hired}\n<i>Fire them first to sign someone new.</i>\n")

    if not staff_list:
        lines.append("\n❌ No staff available in this position right now.")
        buttons = [[InlineKeyboardButton(text="⬅️ Back", callback_data="sm:back")]]
        await callback.message.edit_text(
            "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()
        return

    lines.append(f"\n<b>Available ({len(staff_list)}):</b>")

    # Build buttons — one hire button per staff member
    hire_buttons = []
    for s in staff_list:
        real_tag = " ⭐" if s.is_real else ""
        skill_bar = "█" * (s.skill // 10) + "░" * (10 - s.skill // 10)
        specialty_tag = f" [{s.specialty}]" if s.specialty else ""
        lines.append(
            f"\n{'👑' if s.skill >= 95 else '🔵' if s.skill >= 85 else '⚪'} "
            f"<b>{s.name}</b>{real_tag}{specialty_tag}\n"
            f"   Skill: <code>{skill_bar} {s.skill}/100</code>\n"
            f"   💰 ${s.salary:,}/season | Bonus: +{round((s.performance_bonus-1)*100,1)}%\n"
            f"   🆔 ID: <code>{s.id}</code>"
        )
        btn_label = f"✅ Hire {s.name}" + (" ⭐" if s.is_real else "")
        hire_buttons.append([
            InlineKeyboardButton(text=btn_label, callback_data=f"sm:hire:{s.id}")
        ])

    hire_buttons.append([InlineKeyboardButton(text="⬅️ Back to Positions", callback_data="sm:back")])

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=hire_buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sm:hire:"))
async def cb_sm_hire(callback: CallbackQuery):
    staff_id = int(callback.data.split(":", 2)[2])

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!", show_alert=True)
            return

        staff_res = await db.execute(select(Staff).where(Staff.id == staff_id))
        staff = staff_res.scalar_one_or_none()
        if not staff or not staff.is_available:
            await callback.answer("❌ Staff no longer available!", show_alert=True)
            return

        # Check budget
        if team.budget < staff.salary:
            await callback.answer(
                f"❌ Not enough budget!\nNeed: ${staff.salary:,}\nYours: ${team.budget:,}",
                show_alert=True
            )
            return

        # Check same role already hired
        existing_res = await db.execute(
            select(TeamStaff).join(Staff, TeamStaff.staff_id == Staff.id)
            .where(and_(TeamStaff.team_id == team.id, Staff.role == staff.role))
        )
        if existing_res.scalar_one_or_none():
            await callback.answer(
                f"❌ You already have a {staff.role.replace('_',' ').title()}! Fire them first.",
                show_alert=True
            )
            return

        # Hire
        team.budget -= staff.salary
        staff.is_available = False
        db.add(TeamStaff(team_id=team.id, staff_id=staff.id, salary=staff.salary))
        await db.commit()

    info = POSITION_DETAILS.get(staff.role, {})
    real_badge = " ⭐ F1 Legend!" if staff.is_real else ""
    await callback.message.edit_text(
        f"✅ <b>{staff.name}</b>{real_badge} signed!\n\n"
        f"{info.get('emoji','👤')} <b>{info.get('label', staff.role)}</b>\n"
        f"⚙️ Skill: <b>{staff.skill}/100</b>\n"
        f"💰 Salary: <b>${staff.salary:,}/season</b>\n"
        f"📈 Bonus: <b>+{round((staff.performance_bonus-1)*100,1)}%</b>\n\n"
        f"🏁 <i>{info.get('race_effect','')}</i>\n\n"
        f"Use /mystaff to see your full coaching team.",
    )
    await callback.answer("✅ Hired!")


@router.callback_query(F.data == "sm:mystaff")
async def cb_sm_mystaff(callback: CallbackQuery):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!", show_alert=True)
            return
        res = await db.execute(
            select(TeamStaff, Staff)
            .join(Staff, TeamStaff.staff_id == Staff.id)
            .where(TeamStaff.team_id == team.id)
        )
        hired = res.all()

    if not hired:
        await callback.message.edit_text(
            "👥 <b>My Staff</b>\n\nYou have no staff hired yet.\n\n"
            "Hire staff to get race insights, strategy calls, and car development advice!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back to Market", callback_data="sm:back")]
            ])
        )
        await callback.answer()
        return

    lines = ["👥 <b>My Hired Staff</b>\n"]
    total_salary = 0
    for ts, s in hired:
        info = POSITION_DETAILS.get(s.role, {})
        real_badge = " ⭐" if s.is_real else ""
        lines.append(
            f"{info.get('emoji','👤')} <b>{s.name}</b>{real_badge}\n"
            f"   {info.get('label', s.role)}  |  Skill: {s.skill}/100\n"
            f"   💰 ${ts.salary:,}/season"
        )
        total_salary += ts.salary

    lines.append(f"\n💸 <b>Total Wage Bill: ${total_salary:,}/season</b>")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to Market", callback_data="sm:back")]
        ])
    )
    await callback.answer()


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


# ─────────────────────────────────────────────
# TEAM MENU CALLBACKS (inline buttons)
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("team:menu:"))
async def cb_team_menu(callback: CallbackQuery):
    """Back to team menu"""
    team_id = int(callback.data.split(":")[2])
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return
        data = await TeamService(db).get_with_drivers(team.id)
        drivers = data.get("drivers", [])
        staff = data.get("staff", [])
        sponsors = data.get("sponsors", [])

        driver_text = ""
        for d in drivers:
            dr = d["driver"]
            driver_text += f"\n  🏎️ {safe(dr.name)} ({safe(dr.nationality)}) | Skill: {dr.skill}/100"
        if not driver_text:
            driver_text = "\n  ⚠️ No drivers signed!"

        staff_text = ""
        for s in staff:
            st = s["staff"]
            staff_text += f"\n  👤 {safe(st.name)} ({_role_label(st.role)})"
        if not staff_text:
            staff_text = "\n  ⚠️ No staff hired!"

        car_rating = (team.engine + team.aerodynamics + team.chassis +
                      team.reliability + team.tyres + team.pit_crew) // 6

        text = (
            f"🏎️ <b>{safe(team.name)}</b>\n\n"
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
    await callback.message.edit_text(text, reply_markup=team_menu_kb(team_id))
    await callback.answer()


@router.callback_query(F.data.startswith("team:car:"))
async def cb_team_car(callback: CallbackQuery):
    """Show car stats"""
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        car_rating = (team.engine + team.aerodynamics + team.chassis +
                      team.reliability + team.tyres + team.pit_crew) // 6

        def bar(val):
            filled = val // 10
            return "█" * filled + "░" * (10 - filled)

        text = (
            f"🏎️ <b>Car Stats — {safe(team.name)}</b>\n\n"
            f"Overall Rating: <b>{car_rating}/100</b>\n\n"
            f"⚙️ Engine\n"
            f"  {bar(team.engine)} {team.engine}/100\n\n"
            f"🌬️ Aerodynamics\n"
            f"  {bar(team.aerodynamics)} {team.aerodynamics}/100\n\n"
            f"🏗️ Chassis\n"
            f"  {bar(team.chassis)} {team.chassis}/100\n\n"
            f"🔧 Reliability\n"
            f"  {bar(team.reliability)} {team.reliability}/100\n\n"
            f"🛞 Tyres\n"
            f"  {bar(team.tyres)} {team.tyres}/100\n\n"
            f"🔩 Pit Crew\n"
            f"  {bar(team.pit_crew)} {team.pit_crew}/100\n\n"
            f"💡 Use ⬆️ Upgrade Car to improve stats."
        )
    await callback.message.edit_text(text, reply_markup=team_menu_kb(team.id))
    await callback.answer()


@router.callback_query(F.data.startswith("team:drivers:"))
async def cb_team_drivers(callback: CallbackQuery):
    """Show drivers"""
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        data = await TeamService(db).get_with_drivers(team.id)
        drivers = data.get("drivers", [])

        if not drivers:
            text = (
                f"👨‍🏎️ <b>Drivers — {safe(team.name)}</b>\n\n"
                f"⚠️ No drivers signed!\n\n"
                f"Use /market to browse and sign drivers."
            )
        else:
            text = f"👨‍🏎️ <b>Drivers — {safe(team.name)}</b>\n\n"
            for i, d in enumerate(drivers, 1):
                dr = d["driver"]
                contract = d["contract"]
                slot = "Driver 1" if contract.is_primary else "Driver 2"
                overall = (dr.skill + dr.pace + dr.racecraft + dr.consistency) // 4
                text += (
                    f"{'🥇' if contract.is_primary else '🥈'} <b>{safe(dr.name)}</b> [{slot}]\n"
                    f"  🌍 {safe(dr.nationality)} | 🎂 Age: {dr.age}\n"
                    f"  ⭐ Overall: {overall}/100\n"
                    f"  🏎️ Pace: {dr.pace} | 🎯 Racecraft: {dr.racecraft}\n"
                    f"  📊 Consistency: {dr.consistency} | 🌧️ Wet: {dr.wet_weather}\n"
                    f"  ⚡ Overtaking: {dr.overtaking} | 🛡️ Defence: {dr.defence}\n"
                    f"  💰 Salary: ${contract.salary:,}/yr\n"
                    f"  🏆 Career Wins: {dr.career_wins} | Poles: {dr.career_poles}\n\n"
                )
            text += "Use /selldriver &lt;id&gt; to transfer a driver."

    await callback.message.edit_text(text, reply_markup=team_menu_kb(team.id))
    await callback.answer()


@router.callback_query(F.data.startswith("team:staff:"))
async def cb_team_staff(callback: CallbackQuery):
    """Show staff"""
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        staff_result = await db.execute(
            select(TeamStaff, Staff)
            .join(Staff, TeamStaff.staff_id == Staff.id)
            .where(TeamStaff.team_id == team.id)
        )
        staff_list = staff_result.all()

    if not staff_list:
        text = (
            f"👷 <b>Staff — {safe(team.name)}</b>\n\n"
            f"⚠️ No staff hired!\n\n"
            f"Use /staffmarket to hire staff.\n"
            f"Staff boost your car performance every race."
        )
    else:
        total_salary = sum(ts.salary for ts, s in staff_list)
        total_bonus = 1.0
        for ts, s in staff_list:
            total_bonus *= s.performance_bonus
        total_bonus = min(1.25, total_bonus)

        text = f"👷 <b>Staff — {safe(team.name)}</b>\n\n"
        for ts, s in staff_list:
            real_badge = " ⭐" if getattr(s, "is_real", False) else ""
            text += (
                f"{_role_emoji(s.role)} <b>{safe(s.name)}</b>{real_badge}\n"
                f"  {_role_label(s.role)} | Skill: {s.skill}/100\n"
                f"  Bonus: +{round((s.performance_bonus - 1) * 100, 1)}% | "
                f"Salary: ${ts.salary:,}\n\n"
            )
        text += (
            f"💰 Total Wages: ${total_salary:,}/season\n"
            f"📈 Combined Bonus: +{round((total_bonus - 1) * 100, 1)}%\n\n"
            f"Use /staffmarket to hire more."
        )

    await callback.message.edit_text(text, reply_markup=team_menu_kb(team.id))
    await callback.answer()


@router.callback_query(F.data.startswith("team:facilities:"))
async def cb_team_facilities(callback: CallbackQuery):
    """Show facilities"""
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

    upgrade_costs = {1: 10_000_000, 2: 25_000_000, 3: 50_000_000, 4: 100_000_000}

    def facility_info(level):
        if level >= 5:
            return "MAX LEVEL ✅"
        cost = upgrade_costs.get(level, 100_000_000)
        return f"Level {level}/5 | Upgrade: ${cost:,}"

    def stars(level):
        return "⭐" * level + "☆" * (5 - level)

    text = (
        f"🏭 <b>Facilities — {safe(team.name)}</b>\n\n"
        f"🏗️ <b>Factory</b>\n"
        f"  {stars(team.factory_level)} | {facility_info(team.factory_level)}\n"
        f"  Boosts: Car development speed\n\n"
        f"💨 <b>Wind Tunnel</b>\n"
        f"  {stars(team.wind_tunnel_level)} | {facility_info(team.wind_tunnel_level)}\n"
        f"  Boosts: Aerodynamics upgrades\n\n"
        f"🖥️ <b>Simulator</b>\n"
        f"  {stars(team.simulator_level)} | {facility_info(team.simulator_level)}\n"
        f"  Boosts: Driver consistency\n\n"
        f"🏢 <b>HQ</b>\n"
        f"  {stars(team.hq_level)} | {facility_info(team.hq_level)}\n"
        f"  Boosts: Overall team performance\n\n"
        f"💰 Budget: ${team.budget:,}\n\n"
        f"Use /upgrade to develop facilities."
    )

    await callback.message.edit_text(text, reply_markup=team_menu_kb(team.id))
    await callback.answer()


@router.callback_query(F.data.startswith("team:budget:"))
async def cb_team_budget(callback: CallbackQuery):
    """Show budget breakdown"""
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        data = await TeamService(db).get_with_drivers(team.id)
        drivers = data.get("drivers", [])
        staff = data.get("staff", [])
        sponsors = data.get("sponsors", [])

        driver_salaries = sum(d["contract"].salary for d in drivers)
        staff_salaries = sum(s["contract"].salary for s in staff)
        sponsor_income = sum(sp["sponsor"].reward for sp in sponsors if sp["contract"].is_active)
        total_expenses = driver_salaries + staff_salaries

    text = (
        f"💰 <b>Budget — {safe(team.name)}</b>\n\n"
        f"🏦 Available: <b>${team.budget:,}</b>\n\n"
        f"📤 <b>Expenses (per season):</b>\n"
        f"  👨‍🏎️ Driver Salaries: ${driver_salaries:,}\n"
        f"  👷 Staff Salaries: ${staff_salaries:,}\n"
        f"  ─────────────────\n"
        f"  Total Out: ${total_expenses:,}\n\n"
        f"📥 <b>Income:</b>\n"
        f"  🏆 Active Sponsor Rewards: ${sponsor_income:,}\n"
        f"  🎁 Daily Reward: $500,000\n"
        f"  🏁 Race Prize (win): up to $5,000,000\n\n"
        f"💡 <b>Tips:</b>\n"
        f"  • Use /daily every 24h\n"
        f"  • Win races for big prize money\n"
        f"  • Sign sponsors via /sponsors"
    )

    await callback.message.edit_text(text, reply_markup=team_menu_kb(team.id))
    await callback.answer()


@router.callback_query(F.data.startswith("team:achievements:"))
async def cb_team_achievements(callback: CallbackQuery):
    """Show achievements"""
    from src.models.models import TeamAchievement, Achievement
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        result = await db.execute(
            select(TeamAchievement, Achievement)
            .join(Achievement, TeamAchievement.achievement_id == Achievement.id)
            .where(TeamAchievement.team_id == team.id)
            .order_by(TeamAchievement.earned_at.desc())
        )
        earned = result.all()

    if not earned:
        text = (
            f"🏅 <b>Achievements — {safe(team.name)}</b>\n\n"
            f"No achievements yet!\n\n"
            f"🏆 How to earn achievements:\n"
            f"  • Win your first race\n"
            f"  • Get a podium finish\n"
            f"  • Secure pole position\n"
            f"  • Win in the rain\n"
            f"  • Win the championship\n\n"
            f"Get racing to unlock them! 🏁"
        )
    else:
        text = f"🏅 <b>Achievements — {safe(team.name)}</b>\n\n"
        total_money = sum(a.reward_money for ta, a in earned)
        total_rp = sum(a.reward_rp for ta, a in earned)
        for ta, a in earned:
            text += (
                f"{a.icon} <b>{safe(a.name)}</b>\n"
                f"  {safe(a.description)}\n"
                f"  Earned: {ta.earned_at.strftime('%d %b %Y')}\n\n"
            )
        text += (
            f"Total: <b>{len(earned)}</b> achievement(s)\n"
            f"Rewards earned: ${total_money:,} + {total_rp} RP"
        )

    await callback.message.edit_text(text, reply_markup=team_menu_kb(team.id))
    await callback.answer()


@router.callback_query(F.data.startswith("upgrade:menu:"))
async def cb_upgrade_menu(callback: CallbackQuery):
    """Show upgrade car menu"""
    team_id = int(callback.data.split(":")[2])
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return

        text = (
            f"⬆️ <b>Upgrade Car — {safe(team.name)}</b>\n\n"
            f"Current Stats:\n"
            f"⚙️ Engine:       {team.engine}/100  (+3 costs $8,000,000)\n"
            f"🌬️ Aerodynamics: {team.aerodynamics}/100  (+3 costs $7,000,000)\n"
            f"🏗️ Chassis:      {team.chassis}/100  (+3 costs $7,000,000)\n"
            f"🔧 Reliability:  {team.reliability}/100  (+3 costs $5,000,000)\n"
            f"🛞 Tyres:        {team.tyres}/100  (+3 costs $4,000,000)\n"
            f"🔩 Pit Crew:     {team.pit_crew}/100  (+3 costs $3,000,000)\n\n"
            f"💰 Available: <b>${team.budget:,}</b>\n\n"
            f"Select a stat to upgrade:"
        )

    await callback.message.edit_text(text, reply_markup=upgrade_menu_kb(team_id))
    await callback.answer()


# ─────────────────────────────────────────────
# LEAGUE COMMANDS
# ─────────────────────────────────────────────

@router.message(Command("league"))
@router.message(F.text == "👥 League")
async def cmd_league(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first with /register")
            return

        if not team.league_id:
            await message.answer(
                "👥 <b>League</b>\n\n"
                "You are not in any league yet!\n\n"
                "Use the buttons below to create or join one:",
                reply_markup=league_kb()
            )
            return

        from src.models.models import League
        from sqlalchemy import select as sa_select
        result = await db.execute(sa_select(League).where(League.id == team.league_id))
        league = result.scalar_one_or_none()
        if not league:
            await message.answer("❌ League not found!", reply_markup=league_kb())
            return

        teams_result = await db.execute(
            sa_select(Team).where(Team.league_id == league.id)
        )
        teams = teams_result.scalars().all()
        is_owner = league.owner_id == message.from_user.id

        text = (
            f"👥 <b>{safe(league.name)}</b>\n\n"
            f"📋 {safe(league.description or 'No description')}\n\n"
            f"🔑 Invite Code: <code>{league.invite_code}</code>\n"
            f"📊 Status: {league.status.value.title()}\n"
            f"🏎️ Teams: {len(teams)}/{league.max_teams}\n"
            f"🏆 Season: {league.current_season} | Race: {league.current_race}\n"
            f"👑 Owner: {'You' if is_owner else 'Other'}\n\n"
        )

        if is_owner:
            text += (
                f"<b>Owner Commands:</b>\n"
                f"• /startseason — Start the season\n"
                f"• /runrace — Simulate next race\n"
                f"• /deleteleague — Delete this league\n\n"
            )
        text += "• /leaveleague — Leave this league"

        await message.answer(text, reply_markup=league_kb())


@router.callback_query(F.data == "league:create")
async def cb_league_create(callback: CallbackQuery, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return
        if team.league_id:
            await callback.answer("❌ You're already in a league!", show_alert=True)
            return

    await state.set_state(LeagueCreateStates.waiting_name)
    await callback.message.answer(
        "🏆 <b>Create League</b>\n\n"
        "Enter a name for your league:\n"
        "<i>Max 32 characters</i>"
    )
    await callback.answer()


@router.message(LeagueCreateStates.waiting_name)
async def league_create_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("❌ Too short! Min 3 characters.")
        return
    if len(name) > 32:
        await message.answer("❌ Too long! Max 32 characters.")
        return
    await state.update_data(league_name=name)
    await state.set_state(LeagueCreateStates.waiting_description)
    await message.answer(
        f"✅ Name: <b>{safe(name)}</b>\n\n"
        "Add a description (or type <b>skip</b>):"
    )


@router.message(LeagueCreateStates.waiting_description)
async def league_create_description(message: Message, state: FSMContext):
    desc = "" if message.text.strip().lower() == "skip" else message.text.strip()
    await state.update_data(league_desc=desc)
    await state.set_state(LeagueCreateStates.waiting_password)
    await message.answer(
        "🔒 Set a password to make it private?\n"
        "Type a password or <b>skip</b> for public league:"
    )


@router.message(LeagueCreateStates.waiting_password)
async def league_create_password(message: Message, state: FSMContext):
    data = await state.get_data()
    password = None if message.text.strip().lower() == "skip" else message.text.strip()
    is_public = password is None

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            await state.clear()
            return
        try:
            league = await LeagueService(db).create(
                owner_id=message.from_user.id,
                name=data["league_name"],
                description=data.get("league_desc", ""),
                is_public=is_public,
                password=password,
            )
            team.league_id = league.id
            await db.commit()
            await state.clear()
            await message.answer(
                f"🎉 <b>League Created!</b>\n\n"
                f"🏆 Name: <b>{safe(league.name)}</b>\n"
                f"🔑 Invite Code: <code>{league.invite_code}</code>\n"
                f"🌍 Type: {'Public' if is_public else 'Private 🔒'}\n\n"
                f"Share the invite code with others!\n"
                f"Use /startseason when everyone has joined."
            )
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()


@router.callback_query(F.data == "league:join")
async def cb_league_join(callback: CallbackQuery, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return
        if team.league_id:
            await callback.answer("❌ You're already in a league!", show_alert=True)
            return

    await state.set_state(LeagueJoinStates.waiting_code)
    await callback.message.answer(
        "🔗 <b>Join League</b>\n\n"
        "Enter the 8-character invite code:"
    )
    await callback.answer()


@router.message(LeagueJoinStates.waiting_code)
async def league_join_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if len(code) != 8:
        await message.answer("❌ Invite code must be 8 characters!")
        return
    await state.update_data(invite_code=code)
    await state.set_state(LeagueJoinStates.waiting_password)
    await message.answer(
        f"🔑 Code: <code>{code}</code>\n\n"
        "If this league has a password, enter it.\n"
        "Otherwise type <b>skip</b>:"
    )


@router.message(LeagueJoinStates.waiting_password)
async def league_join_password(message: Message, state: FSMContext):
    data = await state.get_data()
    password = None if message.text.strip().lower() == "skip" else message.text.strip()

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            await state.clear()
            return
        success, msg = await LeagueService(db).join(team.id, data["invite_code"], password)
        await db.commit()

    await state.clear()
    await message.answer("✅ " + msg if success else "❌ " + msg)


@router.callback_query(F.data == "league:public")
async def cb_league_public(callback: CallbackQuery):
    async with get_session() as db:
        leagues = await LeagueService(db).list_public()

    if not leagues:
        await callback.message.answer("😕 No public leagues available right now.")
        await callback.answer()
        return

    text = "🌍 <b>Public Leagues</b>\n\n"
    for lg in leagues:
        text += (
            f"🏆 <b>{safe(lg.name)}</b>\n"
            f"  Code: <code>{lg.invite_code}</code> | Status: {lg.status.value.title()}\n"
            f"  {safe(lg.description or '')}\n\n"
        )
    text += "Use the invite code to join via 🔗 Join League."
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "league:mine")
async def cb_league_mine(callback: CallbackQuery):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team or not team.league_id:
            await callback.message.answer("❌ You are not in any league!")
            await callback.answer()
            return

        from src.models.models import League
        from sqlalchemy import select as sa_select
        result = await db.execute(sa_select(League).where(League.id == team.league_id))
        league = result.scalar_one_or_none()
        teams_result = await db.execute(
            sa_select(Team).where(Team.league_id == league.id)
        )
        teams = teams_result.scalars().all()

    is_owner = league.owner_id == callback.from_user.id
    text = (
        f"👥 <b>{safe(league.name)}</b>\n\n"
        f"🔑 Invite Code: <code>{league.invite_code}</code>\n"
        f"📊 Status: {league.status.value.title()}\n"
        f"🏎️ Teams: {len(teams)}/{league.max_teams}\n"
        f"🏆 Season: {league.current_season}\n"
        f"👑 Owner: {'You ✅' if is_owner else 'Other'}\n\n"
        f"Teams:\n"
    )
    for t in teams:
        text += f"  • {safe(t.name)}\n"

    await callback.message.answer(text)
    await callback.answer()


# ─────────────────────────────────────────────
# /startseason & /runrace — League owner commands
# ─────────────────────────────────────────────

@router.message(Command("startseason"))
async def cmd_startseason(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ You are not in any league!")
            return
        success, msg = await LeagueService(db).start_season(team.league_id, message.from_user.id)
        await db.commit()
    await message.answer("✅ " + msg if success else "❌ " + msg)


@router.message(Command("runrace"))
async def cmd_runrace(message: Message):
    # ── Validation (own short-lived session) ────────────────────────
    from src.models.models import League, LeagueStatus as LS, Race, RaceStatus
    from sqlalchemy import select as sa_select, and_ as sa_and

    weather_emoji = {
        "sunny": "☀️", "cloudy": "🌥️", "light_rain": "🌧️",
        "heavy_rain": "⛈️", "mixed": "🌦️"
    }

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ You are not in any league!")
            return

        league_res = await db.execute(sa_select(League).where(League.id == team.league_id))
        league = league_res.scalar_one_or_none()
        if not league or league.owner_id != message.from_user.id:
            await message.answer("❌ Only the league owner can run races!")
            return

        race_res = await db.execute(
            sa_select(Race).where(
                sa_and(Race.league_id == team.league_id, Race.status == RaceStatus.SCHEDULED)
            ).order_by(Race.round.asc()).limit(1)
        )
        next_race = race_res.scalar_one_or_none()
        if not next_race:
            await message.answer("❌ No scheduled race found! Season may be finished.")
            return

        league_id = team.league_id
        # Capture values before session closes
        announce_text = (
            f"🏎️ <b>ROUND {next_race.round} — {next_race.name.upper()}</b>\n"
            f"🏟️ {next_race.circuit} {next_race.country}\n"
            f"🔢 {next_race.laps} Laps\n\n"
            f"🚦 <b>Race begins in 5 seconds...</b>"
        )

    # ── Announce (outside session — no DB connection held during sleep) ──
    await message.answer(announce_text)
    await asyncio.sleep(5)

    # ── Run simulation in a fresh session ───────────────────────────
    result = None
    try:
        async with get_session() as db:
            result = await RaceService(db).run_race(league_id)
            await db.commit()
    except ValueError as e:
        err = str(e)
        if err.startswith("ALREADY_FINISHED:"):
            race_name = err.split(":", 1)[1]
            await message.answer(
                f"🏁 <b>{safe(race_name)}</b> is already finished!\n\n"
                f"🏆 Use /standings to see the final results."
            )
        else:
            await message.answer(f"❌ {err}")
        return
    except Exception as e:
        logger.error(f"run_race failed: {e}", exc_info=True)
        await message.answer(f"❌ Race simulation error: {e}")
        return

    if not result:
        await message.answer("❌ Race simulation failed or no race to run!")
        return

    raw_events   = result.get("events", [])
    results_list = result.get("results", [])
    race_name    = result.get("race_name", "")
    circuit      = result.get("circuit", "")
    country      = result.get("country", "")
    weather_raw  = result.get("weather", "sunny")
    weather_label = weather_emoji.get(weather_raw, "🌤️")

    # ── Build live commentary chunks (reuse admin engine) ─────────────
    from src.bot.handlers.admin_handlers import build_commentary
    commentary_chunks = build_commentary(raw_events, results_list)

    # ── LIVE BROADCAST — 40s to 90s total ─────────────────────────────
    # Opening shot
    await message.answer(
        f"🔴 <b>LIGHTS OUT AND AWAY WE GO!</b>\n\n"
        f"🏁 <b>{safe(race_name)}</b> — {safe(circuit)} {country}\n"
        f"{weather_label} Weather: {weather_raw.replace('_', ' ').title()}\n\n"
        + (commentary_chunks[0] if commentary_chunks else "🚦 The race is underway!")
    )

    if len(commentary_chunks) > 1:
        # Spread remaining chunks across 40-80 seconds
        broadcast_time = 75  # seconds
        delay = max(4, min(12, broadcast_time // max(len(commentary_chunks) - 1, 1)))

        for chunk in commentary_chunks[1:]:
            await asyncio.sleep(delay)
            is_drama = any(kw in chunk for kw in
                ["SAFETY CAR", "RED FLAG", "RETIREMENT", "overtakes",
                 "VSC", "5 LAPS", "INCIDENT", "CRASH"])
            prefix = "🚨 <b>INCIDENT</b>" if is_drama else "📡 <b>LIVE</b>"
            await message.answer(f"{prefix}\n\n{chunk}")
    else:
        await asyncio.sleep(40)  # minimum race duration even if no events

    # Chequered flag
    await asyncio.sleep(6)
    await message.answer("🏁 <b>CHEQUERED FLAG!</b>\n\nFinal results incoming...")
    await asyncio.sleep(3)

    # ── RACE RESULT IMAGE ──────────────────────────────────────────────
    try:
        from src.services.standings_image import generate_race_standings_image
        from aiogram.types import BufferedInputFile

        img_bytes = generate_race_standings_image(
            race_name=race_name,
            circuit=f"{circuit} {country}",
            weather_label=weather_label,
            results=results_list,
        )

        # Build podium caption
        medals = ["🥇", "🥈", "🥉"]
        podium_lines = []
        for idx, car in enumerate(results_list[:3]):
            if not car.get("dnf"):
                winner_tag = " ✨ WINNER" if idx == 0 else ""
                podium_lines.append(
                    f"{medals[idx]} <b>{safe(car['driver'])}</b> ({safe(car['team'])}){winner_tag}"
                )

        dnf_cars = [c for c in results_list if c.get("dnf")]
        dnf_text = ""
        if dnf_cars:
            dnf_text = "\n\n💥 <b>Retirements:</b> " + ", ".join(
                f"{c['driver']} ({c.get('dnf_reason', 'DNF')})" for c in dnf_cars
            )

        fl_text = ""
        for car in results_list:
            if car.get("fastest_lap"):
                fl_text = f"\n⚡ <b>Fastest Lap:</b> {safe(car['driver'])} 💜"
                break

        caption = (
            f"🏆 <b>RACE RESULT — {safe(race_name)}</b>\n\n"
            + "\n".join(podium_lines)
            + dnf_text
            + fl_text
            + "\n\n✅ Points & standings updated!"
        )

        await message.answer_photo(
            BufferedInputFile(img_bytes, filename="race_result.png"),
            caption=caption,
            parse_mode="HTML",
        )

    except Exception as e:
        logger.warning(f"Race result image failed: {e}")
        # Fallback to text result
        medals = ["🥇", "🥈", "🥉"]
        text = (
            f"🏆 <b>RACE RESULT — {safe(race_name)}</b>\n"
            f"🏟️ {safe(circuit)} {country}\n"
            f"{weather_label} {weather_raw.replace('_', ' ').title()}\n\n"
            f"<b>Results:</b>\n"
        )
        for entry in results_list[:20]:
            pos = entry.get("position")
            if entry.get("dnf"):
                pos_str = "💥"
            elif pos and pos <= 3:
                pos_str = medals[pos - 1]
            elif pos:
                pos_str = f"P{pos}."
            else:
                pos_str = "💥"
            fl = " ⚡" if entry.get("fastest_lap") else ""
            dnf_reason = f" ({safe(entry['dnf_reason'])})" if entry.get("dnf") and entry.get("dnf_reason") else ""
            pts = f" — {entry['points']} pts" if entry.get("points", 0) > 0 else ""
            text += f"{pos_str} {safe(entry['driver'])} <i>({safe(entry['team'])})</i>{fl}{dnf_reason}{pts}\n"
        text += "\n✅ Points & standings updated!"
        await message.answer(text)

    # ── PERSONAL TEAM HIGHLIGHT ──────────────────────────────────────
    # Send every team owner their own result privately (or in-chat if solo)
    if results_list:
        # Find the calling user's team result
        async with get_session() as db_ph:
            my_team = await TeamService(db_ph).get_by_owner(message.from_user.id)
            my_team_id = my_team.id if my_team else None

        if my_team_id:
            my_result = next(
                (r for r in results_list if r.get("team_id") == my_team_id), None
            )
            if my_result:
                pos = my_result.get("position")
                pts = my_result.get("points", 0)
                driver_name = safe(my_result.get("driver", ""))
                fl_tag = "  ⚡ <b>Fastest Lap!</b>" if my_result.get("fastest_lap") else ""
                gap = my_result.get("gap_to_leader")
                gap_str = f"  +{gap:.3f}s to leader" if gap and not my_result.get("dnf") else ""
                pits = my_result.get("pit_stops", 0)

                if my_result.get("dnf"):
                    pos_str = "💥 DNF"
                    reason = f" — {safe(my_result.get('dnf_reason', 'Mechanical'))}"
                    pts_str = "0 points"
                    highlight_color = "❌"
                elif pos == 1:
                    pos_str = "🥇 P1 — VICTORY!"
                    reason = ""
                    pts_str = f"+{pts} pts"
                    highlight_color = "🏆"
                elif pos == 2:
                    pos_str = "🥈 P2 — Podium!"
                    reason = ""
                    pts_str = f"+{pts} pts"
                    highlight_color = "🎉"
                elif pos == 3:
                    pos_str = "🥉 P3 — Podium!"
                    reason = ""
                    pts_str = f"+{pts} pts"
                    highlight_color = "🎉"
                elif pos and pos <= 10:
                    pos_str = f"✅ P{pos} — Points finish"
                    reason = ""
                    pts_str = f"+{pts} pts"
                    highlight_color = "📊"
                else:
                    pos_str = f"P{pos}" if pos else "—"
                    reason = ""
                    pts_str = "0 pts"
                    highlight_color = "📋"

                personal_msg = (
                    f"{highlight_color} <b>YOUR RESULT — {safe(race_name)}</b>\n\n"
                    f"🏎️ Driver: <b>{driver_name}</b>\n"
                    f"🏁 Result: <b>{pos_str}</b>{reason}\n"
                    f"💰 Points: <b>{pts_str}</b>{fl_tag}\n"
                    + (f"⏱️ Gap: {gap_str}\n" if gap_str else "")
                    + f"🔄 Pit Stops: {pits}\n\n"
                    f"<i>/standings — Full championship table</i>"
                )
                await message.answer(personal_msg)

    # ── CIRCUIT INFO CARD ─────────────────────────────────────────────
    try:
        from src.services.circuit_images import generate_circuit_card
        from aiogram.types import BufferedInputFile as BIF2
        circ_bytes = generate_circuit_card(
            race_name=race_name,
            weather=weather_raw,
        )
        await message.answer_photo(
            BIF2(circ_bytes, filename="circuit.png"),
            caption=f"🗺️ <b>{safe(circuit)} {country}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Circuit card failed: {e}")  # circuit image is optional

    # ── TEAM RADIO HIGHLIGHTS ─────────────────────────────────────────
    radio_msgs = result.get("radio_highlights", [])
    if radio_msgs:
        radio_text = "📻 <b>Team Radio Highlights</b>\n\n" + "\n".join(radio_msgs)
        await message.answer(radio_text)

    # ── DRIVER MORALE ALERTS ──────────────────────────────────────────
    morale_alerts = result.get("morale_alerts", [])
    if morale_alerts:
        morale_text = "🧠 <b>Driver Morale Report</b>\n\n" + "\n".join(morale_alerts)
        await message.answer(morale_text)

    # ── SPRINT ROUND NOTICE ───────────────────────────────────────────
    if result.get("is_sprint_round"):
        await message.answer(
            "⚡ <b>Sprint Weekend!</b>\n\n"
            "This is a Sprint round — a short 17-lap race runs before qualifying!\n"
            "Sprint points: P1=8, P2=7 ... P8=1\n\n"
            "Use /sprintrace to run the Sprint Race for this round."
        )

    # ── POST-RACE PRESS CONFERENCE ────────────────────────────────────
    press_q = result.get("press_question")
    if press_q:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔥 Aggressive", callback_data=f"press_aggressive_{press_q['id']}"),
            InlineKeyboardButton(text="🤝 Diplomatic", callback_data=f"press_diplomatic_{press_q['id']}"),
            InlineKeyboardButton(text="😶 Evasive",    callback_data=f"press_evasive_{press_q['id']}"),
        ]])
        await message.answer(
            f"🎤 <b>Post-Race Press Conference</b>\n\n{press_q['question']}\n\n"
            f"<i>Your answer affects team reputation!</i>",
            reply_markup=kb,
        )

    # ── SEASON END GRAND SCREEN ───────────────────────────────────────
    if result.get("season_ended") and result.get("season_summary"):
        ss = result["season_summary"]
        season_num   = ss.get("season_number", "?")
        league_name  = ss.get("league_name", "League")
        constructors = ss.get("constructors", [])
        drivers      = ss.get("drivers", [])
        dev_notifs   = ss.get("dev_notifications", {})
        retired      = ss.get("retired_drivers", [])

        # Build text announcement
        medals = ["🥇", "🥈", "🥉"]
        const_lines = []
        for row in constructors:
            m = medals[row["rank"] - 1] if row["rank"] <= 3 else f"P{row['rank']}"
            crown = " 👑 CHAMPIONS!" if row["rank"] == 1 else ""
            payout_str = f"${row['payout'] // 1_000_000}M prize" if row.get("payout") else ""
            const_lines.append(
                f"{m} <b>{safe(row['team_name'])}</b> — {row['points']} pts{crown}"
                + (f"  💰 {payout_str}" if payout_str else "")
            )
        driver_lines = []
        for row in drivers:
            m = medals[row["rank"] - 1] if row["rank"] <= 3 else f"P{row['rank']}"
            crown = " 🏆 CHAMPION!" if row["rank"] == 1 else ""
            driver_lines.append(f"{m} <b>{safe(row['driver_name'])}</b> — {row['points']} pts{crown}")

        season_text = (
            f"🏁🏆 <b>SEASON {season_num} COMPLETE — {safe(league_name)}</b> 🏆🏁\n\n"
            f"🏗️ <b>Constructor Championship:</b>\n"
            + "\n".join(const_lines or ["No data"])
            + f"\n\n🏎️ <b>Drivers Championship:</b>\n"
            + "\n".join(driver_lines or ["No data"])
            + (f"\n\n🚀 <b>New Season {season_num + 1} begins!</b> Use /startseason to kick off." if constructors else "")
        )
        if retired:
            season_text += f"\n\n👴 <b>Retired this season:</b> {', '.join(retired)}"

        await message.answer(season_text)

        # Championship standings image
        try:
            from src.services.standings_image import generate_constructor_championship_image
            from aiogram.types import BufferedInputFile as BICSI
            champ_img = generate_constructor_championship_image(
                league_name=league_name,
                season=season_num,
                standings=constructors,
                drivers=drivers,
            )
            await message.answer_photo(
                BICSI(champ_img, filename="championship.png"),
                caption=f"🏆 <b>Season {season_num} — Final Constructor Standings</b>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Championship image failed: {e}")

        # Send driver development notifications privately
        if dev_notifs:
            async with get_session() as db_devn:
                from src.models.models import Team as _TM
                from sqlalchemy import select as _sel_dn
                teams_res = await db_devn.execute(
                    _sel_dn(_TM).where(_TM.league_id == team.league_id)
                )
                for t_obj in teams_res.scalars().all():
                    notif = dev_notifs.get(t_obj.id)
                    if notif and t_obj.owner_id:
                        try:
                            await message.bot.send_message(
                                t_obj.owner_id,
                                f"📈 <b>Driver Development Report — End of Season {season_num}</b>\n\n{notif}",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

    # ── PRIVATE STAFF INSIGHTS / POST-RACE DEBRIEF ───────────────────
    staff_insights = result.get("staff_insights", {})
    if staff_insights:
        from sqlalchemy import select as sa_select2
        from src.models.models import Team as TeamModel
        async with get_session() as db2:
            teams_res = await db2.execute(
                sa_select2(TeamModel).where(TeamModel.league_id == team.league_id)
            )
            all_league_teams = teams_res.scalars().all()
        for t in all_league_teams:
            insight_text = staff_insights.get(t.id)
            if insight_text and t.owner_id:
                try:
                    # Find this team's race result for context
                    team_result_entry = next(
                        (r for r in result.get("results", []) if r.get("team_id") == t.id),
                        None
                    )
                    pos_line = ""
                    if team_result_entry:
                        pos = team_result_entry.get("position")
                        pts = team_result_entry.get("points", 0)
                        if team_result_entry.get("dnf"):
                            pos_line = f"\n📋 Result: <b>DNF</b> — {team_result_entry.get('dnf_reason', 'Mechanical')}"
                        elif pos:
                            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                            pos_line = f"\n📋 Result: <b>{medals.get(pos, f'P{pos}')}</b> — {pts} pts"

                    debrief_header = (
                        f"📊 <b>Post-Race Debrief — {safe(race_name)}</b>{pos_line}\n"
                        f"{'─' * 30}\n\n"
                    )
                    await message.bot.send_message(
                        t.owner_id,
                        debrief_header + insight_text,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass


# ─────────────────────────────────────────────
# /deleteteam — Delete your team (with confirmation)
# ─────────────────────────────────────────────

@router.message(Command("deleteteam"))
async def cmd_deleteteam(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ You don't have a team!")
            return

    await state.set_state(DeleteTeamStates.waiting_confirm)
    await message.answer(
        f"⚠️ <b>Team Delete Karna Chahte Ho?</b>\n\n"
        f"Team: <b>{safe(team.name)}</b>\n"
        f"Budget: <b>${team.budget:,}</b>\n\n"
        f"❗ Yeh permanent hai! Sab kuch delete hoga:\n"
        f"Drivers, staff, sponsors, achievements\n\n"
        f"Confirm karne ke liye team ka exact naam type karo:\n"
        f"<code>{safe(team.name)}</code>\n\n"
        f"Cancel karne ke liye /start bhejo"
    )


@router.message(DeleteTeamStates.waiting_confirm)
async def deleteteam_confirm(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Team not found.")
            await state.clear()
            return

        if message.text.strip().lower() != team.name.lower():
            await message.answer(
                f"❌ Naam match nahi kiya!\n\n"
                f"Exact type karo: <code>{safe(team.name)}</code>\n"
                f"Ya cancel ke liye /start bhejo."
            )
            return

        success, msg = await TeamService(db).delete(message.from_user.id)
        await db.commit()

    await state.clear()
    if success:
        await message.answer(
            "✅ <b>Team delete ho gayi!</b>\n\n"
            "Naya team banane ke liye /register use karo.",
            reply_markup=main_menu_kb()
        )
    else:
        await message.answer(f"❌ {msg}")


# ─────────────────────────────────────────────
# /renameteam — Rename your team
# ─────────────────────────────────────────────

@router.message(Command("renameteam"))
async def cmd_renameteam(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ You don't have a team!")
            return

    await state.set_state(RenameTeamStates.waiting_newname)
    await message.answer(
        f"✏️ <b>Rename Team</b>\n\n"
        f"Current name: <b>{safe(team.name)}</b>\n\n"
        f"Naya naam type karo (3-30 characters):\n"
        f"Cancel ke liye /start bhejo."
    )


@router.message(RenameTeamStates.waiting_newname)
async def renameteam_newname(message: Message, state: FSMContext):
    new_name = message.text.strip()
    async with get_session() as db:
        success, result = await TeamService(db).rename(message.from_user.id, new_name)
        await db.commit()

    await state.clear()
    if success:
        await message.answer(f"✅ Team renamed to <b>{safe(result)}</b>!")
    else:
        await message.answer(f"❌ {result}")


# ─────────────────────────────────────────────
# /leaveleague — Leave current league
# ─────────────────────────────────────────────

@router.message(Command("leaveleague"))
async def cmd_leaveleague(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        success, msg = await LeagueService(db).leave(team.id)
        await db.commit()
    await message.answer("✅ " + msg if success else "❌ " + msg)


# ─────────────────────────────────────────────
# /deleteleague — Delete league (owner only, with confirmation)
# ─────────────────────────────────────────────

@router.message(Command("deleteleague"))
async def cmd_deleteleague(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ You are not in any league!")
            return

        from src.models.models import League
        from sqlalchemy import select as sa_select
        result = await db.execute(sa_select(League).where(League.id == team.league_id))
        league = result.scalar_one_or_none()
        if not league or league.owner_id != message.from_user.id:
            await message.answer("❌ Only the league owner can delete the league!")
            return

    await state.update_data(league_id=team.league_id, league_name=league.name)
    await state.set_state(DeleteLeagueStates.waiting_confirm)
    await message.answer(
        f"⚠️ <b>League Delete Karna Chahte Ho?</b>\n\n"
        f"League: <b>{safe(league.name)}</b>\n\n"
        f"❗ Yeh permanent hai! Saari teams league se remove ho jayengi.\n\n"
        f"Confirm karne ke liye league ka exact naam type karo:\n"
        f"<code>{safe(league.name)}</code>\n\n"
        f"Cancel ke liye /start bhejo"
    )


@router.message(DeleteLeagueStates.waiting_confirm)
async def deleteleague_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    league_name = data.get("league_name", "")
    league_id = data.get("league_id")

    if message.text.strip() != league_name:
        await message.answer(
            f"❌ Naam match nahi kiya!\n\n"
            f"Exact type karo: <code>{safe(league_name)}</code>\n"
            f"Ya cancel ke liye /start bhejo."
        )
        return

    force = data.get("force", False)
    async with get_session() as db:
        success, msg = await LeagueService(db).delete(message.from_user.id, league_id, force=force)

    await state.clear()
    await message.answer("✅ " + msg if success else "❌ " + msg)


# ─────────────────────────────────────────────
# /daily — Daily reward
# ─────────────────────────────────────────────

@router.message(Command("daily"))
@router.message(F.text == "🎁 Daily Reward")
async def cmd_daily(message: Message):
    async with get_session() as db:
        result = await UserService(db).claim_daily(message.from_user.id)
        await db.commit()

    if not result:
        await message.answer("❌ Register first!")
        return

    if result["available"]:
        streak = result.get("streak", 1)
        multiplier = result.get("multiplier", 1.0)
        milestone = result.get("milestone_bonus")

        # Streak display
        streak_bar = ""
        for i in range(1, 8):
            streak_bar += "🔥" if i <= streak else "⬜"

        streak_labels = {
            1: "Day 1 — Welcome back!",
            2: "Day 2 — 1.2× Bonus!",
            3: "Day 3 — 1.5× Bonus!",
            4: "Day 4 — 1.8× Bonus! 🔥",
            5: "Day 5 — 2.2× Bonus! 🔥🔥",
            6: "Day 6 — 2.7× Bonus! 🔥🔥🔥",
            7: "Day 7 — MAX STREAK 3.5× Bonus! 🏆",
        }
        streak_label = streak_labels.get(streak, f"Day {streak}")

        text = (
            f"🎁 <b>Daily Reward Claimed!</b>\n\n"
            f"🔥 <b>Login Streak: Day {streak}/7</b>\n"
            f"{streak_bar}\n"
            f"<i>{streak_label}</i>\n\n"
            f"💰 +${result['money']:,}\n"
            f"🔬 +{result['rp']} Research Points\n"
        )

        if multiplier > 1.0:
            text += f"⚡ Streak Multiplier: <b>{multiplier}×</b>\n"

        if milestone:
            text += (
                f"\n🏆 <b>STREAK MILESTONE BONUS!</b>\n"
                f"💰 +${milestone['money']:,}\n"
                f"🔬 +{milestone['rp']} RP\n"
                f"⭐ +{milestone['rep']} Reputation\n"
            )

        next_mult = {1: 1.2, 2: 1.5, 3: 1.8, 4: 2.2, 5: 2.7, 6: 3.5, 7: 1.0}.get(streak, 1.0)
        if streak < 7:
            text += f"\n<i>Come back tomorrow for Day {streak+1} ({next_mult}× multiplier)!</i>"
        else:
            text += f"\n<i>Max streak! Keep it up — resets to Day 1 tomorrow.</i>"

        await message.answer(text)
    else:
        await message.answer(
            f"⏳ Already claimed today!\n\n"
            f"Next reward in: <b>{result['hours']}h {result['minutes']}m</b>"
        )


# ─────────────────────────────────────────────
# /sponsors — Full Sponsor Management
# ─────────────────────────────────────────────

@router.message(Command("sponsors"))
@router.message(F.text == "💰 Sponsors")
async def cmd_sponsors(message: Message):
    from src.bot.keyboards.keyboards import sponsors_kb
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        team_id = team.id

    await message.answer(
        f"💰 <b>Sponsor Management</b>\n\n"
        f"Sponsors pay you every race — but only if you meet their targets.\n"
        f"Fail 3 races in a row and they'll walk away! 😤\n\n"
        f"What would you like to do?",
        reply_markup=sponsors_kb(team_id)
    )


@router.callback_query(F.data.startswith("sponsor:my:"))
async def cb_my_sponsors(callback: CallbackQuery):
    from src.services.game_services import SponsorService
    team_id = int(callback.data.split(":")[2])

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Not registered!", show_alert=True)
            return
        data = await SponsorService(db).get_available_sponsors(team.id)

    active = data.get("active", [])
    tier_emoji = {"small": "🥉", "medium": "🥈", "premium": "🥇", "title": "👑"}

    if not active:
        text = (
            "📋 <b>My Sponsors</b>\n\n"
            "You have no active sponsors!\n\n"
            "<i>Browse available sponsors to sign your first deal.</i>"
        )
    else:
        text = "📋 <b>My Active Sponsors</b>\n\n"
        for ts, sp in active:
            emoji = tier_emoji.get(sp.tier, "🏷️")
            races_left = ts.contract_races - ts.races_completed
            req = f"Top {sp.target_position}" if sp.target_position else f"{sp.target_points}+ pts/race"

            # Failure count from termination_reason temp field
            fail_count = 0
            if ts.termination_reason and ts.termination_reason.startswith("fails:"):
                try:
                    fail_count = int(ts.termination_reason.split(":")[1])
                except Exception:
                    fail_count = 0
            fail_warning = ""
            if fail_count == 1:
                fail_warning = "\n  ⚠️ 1 miss — 2 more and they walk!"
            elif fail_count == 2:
                fail_warning = "\n  🚨 2 misses — ONE MORE and they terminate!"

            text += (
                f"{emoji} <b>{safe(sp.name)}</b> [{sp.tier.title()}]\n"
                f"  💰 Reward: <b>${sp.reward:,}/race</b>\n"
                f"  🎯 Target: <b>{req}</b>\n"
                f"  ⚠️ Penalty if missed: <b>${sp.penalty:,}</b>\n"
                f"  📋 Races left: <b>{races_left}</b>\n"
                f"  💵 Total earned: <b>${ts.total_earned:,}</b>"
                f"{fail_warning}\n\n"
            )

    from src.bot.keyboards.keyboards import sponsors_kb
    await callback.message.edit_text(text, reply_markup=sponsors_kb(team_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sponsor:browse:"))
async def cb_browse_sponsors(callback: CallbackQuery):
    from src.services.game_services import SponsorService
    parts = callback.data.split(":")
    team_id, page = int(parts[2]), int(parts[3])

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Not registered!", show_alert=True)
            return
        data = await SponsorService(db).get_available_sponsors(team.id)

    available = data.get("available", [])
    locked = data.get("locked", [])
    tier_emoji = {"small": "🥉", "medium": "🥈", "premium": "🥇", "title": "👑"}
    tier_desc = {
        "small": "Small regional sponsor. Easy targets, low reward.",
        "medium": "Mid-tier brand. Good pay if you perform consistently.",
        "premium": "Major corporation. High reward, demanding targets.",
        "title": "Title sponsor. Life-changing money, but you must WIN.",
    }

    text = f"🔍 <b>Available Sponsors</b>\n📊 Your Reputation: <b>{team.reputation}/100</b>\n\n"

    if available:
        text += "✅ <b>You Qualify For:</b>\n\n"
        for sp in available:
            emoji = tier_emoji.get(sp.tier, "🏷️")
            req = f"Finish Top {sp.target_position}" if sp.target_position else f"Score {sp.target_points}+ pts"
            text += (
                f"{emoji} <b>{safe(sp.name)}</b>\n"
                f"  <i>{tier_desc.get(sp.tier, '')}</i>\n"
                f"  💰 <b>${sp.reward:,}/race</b> (5 races)\n"
                f"  🎯 Requirement: <b>{req}</b>\n"
                f"  ⚠️ Miss penalty: <b>${sp.penalty:,}</b>\n"
                f"  Use: /signsponsor {sp.id}\n\n"
            )
    else:
        text += "❌ No sponsors available at your reputation level.\n\n"

    if locked:
        text += "🔒 <b>Locked (Need More Reputation):</b>\n\n"
        for sp in locked[:5]:
            emoji = tier_emoji.get(sp.tier, "🏷️")
            text += (
                f"{emoji} <b>{safe(sp.name)}</b> — Need <b>{sp.min_reputation}</b> rep "
                f"(you have {team.reputation})\n"
            )

    from src.bot.keyboards.keyboards import sponsors_kb
    await callback.message.edit_text(text, reply_markup=sponsors_kb(team_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sponsor:terminate_menu:"))
async def cb_terminate_menu(callback: CallbackQuery):
    from src.services.game_services import SponsorService
    from src.bot.keyboards.keyboards import sponsor_terminate_kb, sponsors_kb
    team_id = int(callback.data.split(":")[2])

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Not registered!", show_alert=True)
            return
        data = await SponsorService(db).get_available_sponsors(team.id)

    active = data.get("active", [])
    if not active:
        await callback.answer("You have no active sponsors to terminate!", show_alert=True)
        return

    tier_emoji = {"small": "🥉", "medium": "🥈", "premium": "🥇", "title": "👑"}
    text = "❌ <b>Terminate Sponsor Contract</b>\n\n"
    text += "Select which sponsor to terminate:\n\n"

    builder = InlineKeyboardBuilder()
    for ts, sp in active:
        emoji = tier_emoji.get(sp.tier, "🏷️")
        races_left = ts.contract_races - ts.races_completed
        exit_fee = int(sp.reward * races_left * 0.5)
        text += (
            f"{emoji} <b>{safe(sp.name)}</b>\n"
            f"  Races left: {races_left} | Early exit fee: ${exit_fee:,}\n\n"
        )
        builder.row(
            InlineKeyboardButton(
                text=f"❌ Drop {sp.name}",
                callback_data=f"sponsor:terminate_confirm:{team_id}:{sp.id}"
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data=f"sponsor:my:{team_id}"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("sponsor:terminate_confirm:"))
async def cb_terminate_confirm(callback: CallbackQuery):
    from src.bot.keyboards.keyboards import sponsor_terminate_kb
    parts = callback.data.split(":")
    team_id, sponsor_id = int(parts[2]), int(parts[3])

    async with get_session() as db:
        sp_res = await db.execute(select(Sponsor).where(Sponsor.id == sponsor_id))
        sp = sp_res.scalar_one_or_none()
        if not sp:
            await callback.answer("Sponsor not found!", show_alert=True)
            return
        ts_res = await db.execute(
            select(TeamSponsor).where(
                and_(TeamSponsor.team_id == team_id,
                     TeamSponsor.sponsor_id == sponsor_id,
                     TeamSponsor.is_active == True)
            )
        )
        ts = ts_res.scalar_one_or_none()
        if not ts:
            await callback.answer("No active contract!", show_alert=True)
            return
        races_left = ts.contract_races - ts.races_completed
        exit_fee = int(sp.reward * races_left * 0.5)

    text = (
        f"⚠️ <b>Terminate Contract — {safe(sp.name)}</b>\n\n"
        f"📋 Races left on contract: <b>{races_left}</b>\n"
        f"💸 Early exit fee: <b>${exit_fee:,}</b> (50% of remaining value)\n"
        f"⭐ Reputation hit: <b>-5</b>\n\n"
        f"<b>Are you sure you want to drop this sponsor?</b>\n\n"
        f"<i>Once terminated, they may not offer you a deal again for a while.</i>"
    )
    await callback.message.edit_text(text, reply_markup=sponsor_terminate_kb(team_id, sponsor_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sponsor:terminate:"))
async def cb_terminate_sponsor(callback: CallbackQuery):
    from src.services.game_services import SponsorService
    from src.bot.keyboards.keyboards import sponsors_kb
    parts = callback.data.split(":")
    team_id, sponsor_id = int(parts[2]), int(parts[3])
    mode = parts[4] if len(parts) > 4 else "early"

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Not registered!", show_alert=True)
            return
        success, msg = await SponsorService(db).terminate_sponsor(team.id, sponsor_id, early_exit=True)
        await db.commit()

    await callback.message.edit_text(msg, reply_markup=sponsors_kb(team_id))
    await callback.answer("✅ Done" if success else "❌ Failed", show_alert=not success)


@router.message(Command("signsponsor"))
async def cmd_sign_sponsor(message: Message):
    from src.services.game_services import SponsorService
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /signsponsor <sponsor_id>\n\nFind sponsor IDs with /sponsors → Find Sponsors")
        return
    try:
        sponsor_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid sponsor ID!")
        return

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        success, msg = await SponsorService(db).sign_sponsor(team.id, sponsor_id)
        await db.commit()

    await message.answer(msg)


# ─────────────────────────────────────────────
# /research — Research tree (beginner-friendly)
# ─────────────────────────────────────────────

TREE_INFO = {
    "power_unit": {
        "label": "⚡ Power Unit",
        "emoji": "⚡",
        "what_it_is": (
            "The engine + hybrid system. In F1, power units have 6 components: "
            "ICE (engine), turbo, MGU-H, MGU-K, energy store, and control electronics. "
            "The MGU-K recovers energy under braking and boosts the car on straights."
        ),
        "why_it_matters": (
            "A powerful engine = faster on straights. Crucial at Monza 🇮🇹 (Spa 🇧🇪, Baku 🇦🇿 etc.). "
            "Weak engine = you get overtaken on every straight, no matter how good your aero is."
        ),
        "stat": "engine",
    },
    "aero": {
        "label": "🌬️ Aerodynamics",
        "emoji": "🌬️",
        "what_it_is": (
            "How air flows around the car. F1 cars use wings, diffusers, and floors to generate "
            "downforce — the invisible force that pushes the car INTO the track, letting it corner faster. "
            "More downforce = faster corners. Less downforce (low drag) = faster straights."
        ),
        "why_it_matters": (
            "Aero is king at twisty circuits like Hungary 🇭🇺, Monaco 🇲🇨, Singapore 🇸🇬. "
            "A car with great aero can corner 20 km/h faster than rivals, making up huge time through the lap."
        ),
        "stat": "aerodynamics",
    },
    "weight_reduction": {
        "label": "⚖️ Weight Reduction",
        "emoji": "⚖️",
        "what_it_is": (
            "F1 cars must weigh at least 798 kg (with driver). Teams use carbon fibre, titanium, "
            "and exotic alloys to hit the minimum. Every 10 kg saved is roughly 0.3 seconds per lap."
        ),
        "why_it_matters": (
            "A lighter car accelerates faster, brakes later, and is easier on tyres. "
            "Improves chassis stat which helps everywhere, but especially in slow-speed sections."
        ),
        "stat": "chassis",
    },
    "reliability": {
        "label": "🔧 Reliability",
        "emoji": "🔧",
        "what_it_is": (
            "How rarely your car breaks down. F1 cars are pushed to absolute limits — "
            "engines rev to 15,000 RPM, brakes hit 1,000°C. One failed hydraulic seal = DNF."
        ),
        "why_it_matters": (
            "A DNF (Did Not Finish) = 0 points + sponsor penalty + budget waste. "
            "High reliability means more race finishes = consistent points = better standings. "
            "Ask Honda circa 2015 why reliability matters... 💀"
        ),
        "stat": "reliability",
    },
    "tyres": {
        "label": "🛞 Tyre Technology",
        "emoji": "🛞",
        "what_it_is": (
            "Pirelli supplies all F1 teams the same tyres, but teams differ in how they manage them. "
            "Tyre temperature window, degradation models, compound choice — it's a science. "
            "Thermal management keeps tyres in the optimal 90–110°C window."
        ),
        "why_it_matters": (
            "Good tyre tech = longer stints, fewer pit stops, and consistent lap times. "
            "At high-deg circuits like Qatar 🇶🇦 and Spain 🇪🇸, a team with better tyre management "
            "can run 5 laps longer per stint — that's a free pit stop advantage over rivals."
        ),
        "stat": "tyres",
    },
}


@router.message(Command("research"))
@router.message(F.text == "🔬 Research")
async def cmd_research(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        team_rp = team.research_points
        team_budget = team.budget
        team_id = team.id

    text = (
        f"🔬 <b>Research & Development</b>\n\n"
        f"🧪 Research Points: <b>{team_rp} RP</b>\n"
        f"💰 Budget: <b>${team_budget:,}</b>\n\n"
        f"<b>What is R&D?</b>\n"
        f"Research Points (RP) are earned from races and daily rewards. "
        f"Spend them here to develop your car. Each upgrade permanently boosts a stat.\n\n"
        f"<b>Choose a research tree to explore:</b>"
    )
    await message.answer(text, reply_markup=research_kb(team_id))


@router.callback_query(F.data.startswith("research:tree:"))
async def cb_research_tree(callback: CallbackQuery):
    parts = callback.data.split(":")
    team_id, tree = int(parts[2]), parts[3]

    async with get_session() as db:
        team = await TeamService(db).get_by_owner(callback.from_user.id)
        if not team:
            await callback.answer("❌ Register first!")
            return
        status = await ResearchService(db).get_tree_status(team.id, tree)
        team_rp = team.research_points
        team_budget = team.budget
        team_id = team.id

    info = TREE_INFO.get(tree, {})
    label = info.get("label", tree)
    stat_name = info.get("stat", "").replace("_", " ").title()

    # Get current stat value
    stat_val = getattr(team, info.get("stat", "engine"), 50) if team else 50

    text = (
        f"{info.get('emoji', '🔬')} <b>{label}</b>\n\n"
        f"📖 <b>What is it?</b>\n{info.get('what_it_is', '')}\n\n"
        f"🏎️ <b>Why does it matter?</b>\n{info.get('why_it_matters', '')}\n\n"
        f"📊 Your current <b>{stat_name}</b>: <b>{stat_val}/100</b>\n"
        f"🧪 Your RP: <b>{team_rp}</b> | 💰 Budget: <b>${team_budget:,}</b>\n\n"
        f"<b>Upgrade Nodes:</b>\n\n"
    )

    nodes = status.get("nodes", [])
    if not nodes:
        text += "No nodes available."
    else:
        for i, node in enumerate(nodes):
            done = "✅" if node.get("done") else "🔒"
            # Show if affordable
            can_afford_rp = team_rp >= node["rp_cost"]
            can_afford_money = team_budget >= node["money_cost"]
            if node.get("done"):
                afford_tag = ""
            elif can_afford_rp and can_afford_money:
                afford_tag = " ✨ <i>(affordable!)</i>"
            elif not can_afford_rp:
                afford_tag = f" <i>(need {node['rp_cost'] - team_rp} more RP)</i>"
            else:
                afford_tag = f" <i>(need ${node['money_cost'] - team_budget:,} more)</i>"

            text += (
                f"{done} <b>Node {i+1}: {safe(node['name'])}</b>{afford_tag}\n"
                f"  💸 Cost: <b>{node['rp_cost']} RP</b> + <b>${node['money_cost']:,}</b>\n"
                f"  📈 Bonus: <b>+{node['bonus']}</b> to {stat_name}\n"
            )
            if not node.get("done"):
                text += f"  ▶️ Unlock: <code>/research {tree} {node['node']}</code>\n"
            text += "\n"

    await callback.message.edit_text(text, reply_markup=research_kb(team_id))
    await callback.answer()


@router.message(Command("research", magic=F.args != None))
async def cmd_research_buy(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        return  # handled by the no-args handler above

    tree, node_key = parts[1], parts[2]
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        success, msg = await ResearchService(db).start_research(team.id, tree, node_key)
        await db.commit()

    if success:
        # Add context about what was improved
        info = TREE_INFO.get(tree, {})
        stat = info.get("stat", "")
        await message.answer(
            f"✅ {msg}\n\n"
            f"<i>Your car is now faster! Head to the next race to feel the difference.</i>",
        )
    else:
        await message.answer("❌ " + msg)




# ─────────────────────────────────────────────
# /forceleaveleague — Leave mid-season (forced)
# ─────────────────────────────────────────────

@router.message(Command("forceleaveleague"))
async def cmd_forceleaveleague(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        success, msg = await LeagueService(db).leave(team.id, force=True)
        await db.commit()
    await message.answer("✅ " + msg if success else "❌ " + msg)


# ─────────────────────────────────────────────
# /forcedeleteleague — Delete mid-season (owner, forced)
# ─────────────────────────────────────────────

@router.message(Command("forcedeleteleague"))
async def cmd_forcedeleteleague(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team or not team.league_id:
            await message.answer("❌ You are not in any league!")
            return

        from src.models.models import League
        from sqlalchemy import select as sa_select
        result = await db.execute(sa_select(League).where(League.id == team.league_id))
        league = result.scalar_one_or_none()
        if not league or league.owner_id != message.from_user.id:
            await message.answer("❌ Only the league owner can delete the league!")
            return

    await state.update_data(league_id=team.league_id, league_name=league.name, force=True)
    await state.set_state(DeleteLeagueStates.waiting_confirm)
    await message.answer(
        f"⚠️ <b>FORCE DELETE — League</b>\n\n"
        f"League: <b>{safe(league.name)}</b>\n\n"
        f"❗ Season active hai phir bhi delete hoga!\n"
        f"Saari teams league se remove ho jayengi.\n\n"
        f"Confirm karne ke liye league ka exact naam type karo:\n"
        f"<code>{safe(league.name)}</code>\n\n"
        f"Cancel ke liye /start bhejo"
    )

# ─────────────────────────────────────────────
# /help — Command list
# ─────────────────────────────────────────────

# /help is handled by onboarding_handlers.py (categorized + topics)


# ─────────────────────────────────────────────
# NEXT RACE
# ─────────────────────────────────────────────

@router.message(Command("nextrace"))
async def cmd_nextrace(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first with /register!")
            return
        if not team.league_id:
            await message.answer("❌ Join a league first!")
            return

        from src.models.models import League, Race, RaceStatus as RS
        from sqlalchemy import select, and_

        # Get league info
        league_res = await db.execute(select(League).where(League.id == team.league_id))
        league = league_res.scalar_one_or_none()

        # Get next scheduled race
        race_res = await db.execute(
            select(Race).where(
                and_(Race.league_id == team.league_id, Race.status == RS.SCHEDULED)
            ).order_by(Race.round.asc()).limit(1)
        )
        race = race_res.scalar_one_or_none()

        if not race:
            await message.answer(
                "🏁 <b>Season Complete!</b>\n\n"
                "Saari races ho gayi hain. Admin se season wrap-up ka wait karo.\n"
                "Check /standings for final standings."
            )
            return

        # Count finished races
        finished_res = await db.execute(
            select(Race).where(
                and_(Race.league_id == team.league_id, Race.status == RS.FINISHED)
            )
        )
        finished_count = len(finished_res.scalars().all())
        total_races = league.total_races if hasattr(league, "total_races") else 24

        await message.answer(
            f"🏎️ <b>Next Race — Round {race.round}</b>\n\n"
            f"{race.country} <b>{race.name}</b>\n"
            f"🏟️ {race.circuit}\n"
            f"🔢 {race.laps} Laps\n\n"
            f"📊 Season Progress: {finished_count}/{total_races} races done\n\n"
            f"💡 Race ke liye:\n"
            f"  • /strategy — Apni race strategy set karo\n"
            f"  • /practice — Practice session karo\n"
            f"  • /budget — Budget check karo"
        )


# ─────────────────────────────────────────────
# PRESS CONFERENCE CALLBACK
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("press_"))
async def cb_press_answer(callback: CallbackQuery):
    """Handle press conference answer buttons."""
    from src.services.f1_features import PRESS_QUESTIONS, apply_press_answer
    parts = callback.data.split("_", 2)   # press_{type}_{q_id}
    if len(parts) < 3:
        await callback.answer("Invalid response.")
        return

    answer_type = parts[1]   # aggressive / diplomatic / evasive
    q_id        = parts[2]

    question = next((q for q in PRESS_QUESTIONS if q["id"] == q_id), None)
    if not question:
        await callback.answer("Question not found.")
        return

    rep_change, rival_change, response_text = apply_press_answer(answer_type, question)

    # Apply reputation change
    if rep_change != 0:
        async with get_session() as db:
            team = await TeamService(db).get_by_owner(callback.from_user.id)
            if team:
                team.reputation = max(0, min(100, team.reputation + rep_change))
                await db.commit()

    rep_emoji = "📈" if rep_change > 0 else ("📉" if rep_change < 0 else "➡️")
    await callback.message.edit_text(
        f"🎤 <b>Press Conference</b>\n\n"
        f"<i>{question['question']}</i>\n\n"
        f"Your answer: <b>{answer_type.capitalize()}</b>\n"
        f"{response_text}\n\n"
        f"{rep_emoji} Reputation: <b>{rep_change:+d}</b>",
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────────────
# /sprintrace — Run Sprint Race for sprint weekends
# ─────────────────────────────────────────────

@router.message(Command("sprintrace"))
async def cmd_sprintrace(message: Message):
    """Run the Sprint Race for a sprint round weekend."""
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Pehle team banao: /createteam")
            return
        if not team.league_id:
            await message.answer("❌ Kisi league mein join karo pehle: /joinleague")
            return

        from src.models.models import Race, RaceStatus as RS, League
        from sqlalchemy import and_

        # Get next scheduled race
        race_res = await db.execute(
            select(Race).where(
                and_(Race.league_id == team.league_id,
                     Race.status == RS.SCHEDULED)
            ).order_by(Race.round.asc()).limit(1)
        )
        race = race_res.scalar_one_or_none()
        if not race:
            await message.answer("❌ Koi scheduled race nahi hai abhi.")
            return

        # Check if it's a sprint round
        from src.core.config import F1_CALENDAR
        cal_entry = next((r for r in F1_CALENDAR if r["name"] == race.name), {})
        if not cal_entry.get("sprint"):
            await message.answer(
                f"❌ <b>{safe(race.name)}</b> sprint round nahi hai.\n\n"
                f"Sprint rounds: China, Austria, Belgium, USA, Brazil, Qatar"
            )
            return

    await message.answer(f"⚡ <b>Sprint Race — {safe(race.name)}</b>\n\nSimulating 17-lap sprint... please wait.")

    # Build entries same as main race
    async with get_session() as db:
        from src.services.game_services import RaceService
        entries = await RaceService(db)._build_entries(team.league_id)

    if not entries:
        await message.answer("❌ No entries built for sprint race.")
        return

    from src.services.f1_features import simulate_sprint_race
    sprint_result = await asyncio.to_thread(simulate_sprint_race, entries, race.name)

    # Show events
    events_text = "\n".join(sprint_result.get("events", []))
    if len(events_text) > 3800:
        events_text = events_text[:3800] + "\n..."
    await message.answer(events_text)

    # Build result card
    results = sprint_result.get("results", [])
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for r in results[:8]:  # top 8 get points
        pos = r.get("position")
        if r.get("dnf"):
            lines.append(f"💥 DNF — {safe(r['driver'])} ({safe(r['team'])})")
        else:
            pos_str = medals[pos-1] if pos and pos <= 3 else f"P{pos}"
            pts = r.get("points", 0)
            pts_str = f" +{pts}pts" if pts else ""
            lines.append(f"{pos_str} {safe(r['driver'])} ({safe(r['team'])}){pts_str}")

    # Apply sprint points to DB teams
    async with get_session() as db:
        for r in results:
            if r.get("points", 0) > 0 and r.get("team_id", -1) > 0:
                from src.models.models import Team as TM, ConstructorStanding
                team_obj = await db.get(TM, r["team_id"])
                if team_obj:
                    team_obj.total_points = (team_obj.total_points or 0) + r["points"]
        await db.commit()

    sprint_text = (
        f"⚡ <b>Sprint Race Result — {safe(race.name)}</b>\n\n"
        + "\n".join(lines)
        + "\n\n🏎️ Main race: /runrace"
    )
    await message.answer(sprint_text)
