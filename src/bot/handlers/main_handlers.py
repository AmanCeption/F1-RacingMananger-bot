"""
Bot Handlers - Registration, Team, Race, Standings
"""
import logging
import asyncio
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
        await message.answer(
            f"🎁 <b>Daily Reward Claimed!</b>\n\n"
            f"💰 +${result['money']:,}\n"
            f"🔬 +{result['rp']} Research Points\n\n"
            f"Come back in 24 hours for your next reward!"
        )
    else:
        await message.answer(
            f"⏳ Already claimed today!\n\n"
            f"Next reward in: <b>{result['hours']}h {result['minutes']}m</b>"
        )


# ─────────────────────────────────────────────
# /sponsors — View and sign sponsors
# ─────────────────────────────────────────────

@router.message(Command("sponsors"))
@router.message(F.text == "💰 Sponsors")
async def cmd_sponsors(message: Message):
    from src.simulation.driver_db import SPONSORS
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return

        data = await TeamService(db).get_with_drivers(team.id)
        active_sponsors = data.get("sponsors", [])

    text = "💰 <b>Sponsors</b>\n\n"

    if active_sponsors:
        text += "<b>Your Active Sponsors:</b>\n"
        for sp_data in active_sponsors:
            sp = sp_data["sponsor"]
            contract = sp_data["contract"]
            text += (
                f"  🏷️ <b>{safe(sp.name)}</b> [{sp.tier.title()}]\n"
                f"  Reward: ${sp.reward:,} | Races left: {sp.contract_races - contract.races_completed}\n\n"
            )
    else:
        text += "No active sponsors.\n\n"

    text += "<b>Available Sponsors:</b>\n"
    tier_emoji = {"small": "🥉", "medium": "🥈", "premium": "🥇", "title": "👑"}
    for sp in SPONSORS[:10]:
        emoji = tier_emoji.get(sp.get("tier", "small"), "🏷️")
        req = f"Top {sp['target_position']}" if sp.get("target_position") else f"{sp.get('target_points', 0)}+ pts"
        text += (
            f"{emoji} <b>{safe(sp['name'])}</b>\n"
            f"  ${sp['reward']:,} | Req: {req} | Min Rep: {sp.get('min_reputation', 0)}\n"
        )

    text += "\n<i>Sponsors pay out automatically after each race based on performance.</i>"
    await message.answer(text)


# ─────────────────────────────────────────────
# /research — Research tree
# ─────────────────────────────────────────────

@router.message(Command("research"))
@router.message(F.text == "🔬 Research")
async def cmd_research(message: Message):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)
        if not team:
            await message.answer("❌ Register first!")
            return
        team_rp = team.research_points
        team_id = team.id

    await message.answer(
        f"🔬 <b>Research & Development</b>\n\n"
        f"Research Points: <b>{team_rp}</b>\n\n"
        f"Choose a research tree to develop:",
        reply_markup=research_kb(team_id)
    )


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
        team_id = team.id

    tree_labels = {
        "power_unit": "⚡ Power Unit",
        "aero": "🌬️ Aerodynamics",
        "weight_reduction": "⚖️ Weight Reduction",
        "reliability": "🔧 Reliability",
        "tyres": "🛞 Tyre Tech",
    }

    text = (
        f"🔬 <b>{tree_labels.get(tree, tree)}</b>\n\n"
        f"Research Points: <b>{team_rp}</b>\n\n"
    )

    nodes = status.get("nodes", [])
    if not nodes:
        text += "No research nodes available."
    else:
        for node in nodes:
            done = "✅" if node.get("done") else "🔒"
            stat_label = node.get("stat", "").replace("_", " ").title()
            text += (
                f"{done} <b>{safe(node['name'])}</b>\n"
                f"  Cost: {node['rp_cost']} RP + ${node['money_cost']:,}\n"
                f"  Bonus: +{node['bonus']} to {stat_label}\n"
                f"  Use: /research {tree} {node['node']}\n\n"
            )

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
    await message.answer("✅ " + msg if success else "❌ " + msg)




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
