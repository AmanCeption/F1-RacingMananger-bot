"""
Onboarding & Help Handlers
- Guided step-by-step tutorial for new users (/tutorial)
- Improved /help with categories and examples
- Inline driver/staff search (/search)
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import hashlib

from src.core.database.session import get_session
from src.services.game_services import TeamService
from sqlalchemy import select
from src.models.models import Driver, Staff

logger = logging.getLogger(__name__)
router = Router()


def safe(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─────────────────────────────────────────────
# FSM — Tutorial Steps
# ─────────────────────────────────────────────

class TutorialStates(StatesGroup):
    step_team     = State()
    step_drivers  = State()
    step_strategy = State()
    step_league   = State()


# ─────────────────────────────────────────────
# TUTORIAL ENTRY
# ─────────────────────────────────────────────

def tutorial_nav_kb(next_cb: str, skip_cb: str = "tutorial:done") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="▶️ Next", callback_data=next_cb),
        InlineKeyboardButton(text="✅ Done", callback_data=skip_cb),
    )
    return builder.as_markup()


@router.message(Command("tutorial"))
async def cmd_tutorial(message: Message, state: FSMContext):
    async with get_session() as db:
        team = await TeamService(db).get_by_owner(message.from_user.id)

    has_team = team is not None
    await state.set_state(TutorialStates.step_team)

    text = (
        "🏁 <b>Welcome to F1 Racing Manager!</b>\n\n"
        "This quick guide will walk you through everything.\n"
        "Takes about 2 minutes. Let's go. 🔥\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📍 <b>Step 1 of 4 — Your Team</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Every manager runs a team.\n"
        "Your team has:\n"
        "  🏎️ A name and identity\n"
        "  💰 A starting budget of $100,000,000\n"
        "  🔧 Car stats (Engine, Aero, Chassis...)\n"
        "  🏭 Facilities to upgrade\n\n"
    )

    if has_team:
        text += f"✅ You already have a team: <b>{safe(team.name)}</b>\nTap Next to continue."
    else:
        text += "👉 Use /register to create your team first.\nThen come back and tap Next."

    await message.answer(text, reply_markup=tutorial_nav_kb("tutorial:step2"))


@router.callback_query(F.data == "tutorial:step2")
async def tutorial_step2(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TutorialStates.step_drivers)
    await callback.message.edit_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📍 <b>Step 2 of 4 — Drivers</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Every team needs 2 drivers.\n"
        "You can sign:\n"
        "  🌟 <b>Real F1 stars</b> — Verstappen, Hamilton, Leclerc...\n"
        "  🆕 <b>Fictional talents</b> — cheaper, but may surprise you\n\n"
        "Each driver has stats:\n"
        "  ⚡ Pace — raw one-lap speed\n"
        "  🎯 Racecraft — race intelligence\n"
        "  🔄 Consistency — lap-to-lap reliability\n"
        "  🌧️ Wet Weather — performance in rain\n"
        "  🔀 Overtaking / 🛡️ Defence\n\n"
        "👉 Go to <b>/market</b> → Free Agents to sign your first driver.\n"
        "💡 Tip: Balance budget and skill — top drivers cost $20M+/year.",
        reply_markup=tutorial_nav_kb("tutorial:step3"),
    )


@router.callback_query(F.data == "tutorial:step3")
async def tutorial_step3(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TutorialStates.step_strategy)
    await callback.message.edit_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📍 <b>Step 3 of 4 — Race Strategy</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Before each race, set your strategy.\n\n"
        "🛣️ <b>Stop strategies:</b>\n"
        "  1-Stop → slower but fewer tyre changes\n"
        "  2-Stop → balanced (most common)\n"
        "  3-Stop → aggressive, risky but fast\n\n"
        "🛞 <b>Starting tyres:</b>\n"
        "  🔴 Soft — fastest, wears quickly\n"
        "  🟡 Medium — balanced\n"
        "  ⚪ Hard — slowest, lasts longest\n\n"
        "🌧️ <b>Weather matters!</b>\n"
        "  Rain → switch to Intermediates or Wets\n"
        "  Wrong tyre in wet = massive time loss\n\n"
        "👉 Use <b>/strategy</b> before each race.\n"
        "👉 Use <b>/practice</b> to see a circuit preview.",
        reply_markup=tutorial_nav_kb("tutorial:step4"),
    )


@router.callback_query(F.data == "tutorial:step4")
async def tutorial_step4(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TutorialStates.step_league)
    await callback.message.edit_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📍 <b>Step 4 of 4 — Leagues & Competition</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Leagues are where you compete against other managers.\n\n"
        "🌍 <b>Public leagues</b> — join and play with strangers\n"
        "🔒 <b>Private leagues</b> — invite code + optional password\n\n"
        "Each league has:\n"
        "  📅 A 24-race season\n"
        "  🏆 Constructor Championship (your team)\n"
        "  👤 Driver Championship (your drivers)\n"
        "  💰 Prize money for top finishers\n\n"
        "👉 Use <b>/league</b> to create or join a league.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "That's it! You're ready to race. 🏎️",
        reply_markup=tutorial_nav_kb("tutorial:done", "tutorial:done"),
    )


@router.callback_query(F.data == "tutorial:done")
async def tutorial_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "✅ <b>Tutorial complete!</b>\n\n"
        "Here's your quick-start checklist:\n\n"
        "☐ /register — Create your team\n"
        "☐ /market — Sign 2 drivers\n"
        "☐ /upgrade — Improve your car\n"
        "☐ /league — Join a league\n"
        "☐ /strategy — Set race strategy\n"
        "☐ /daily — Claim daily reward\n\n"
        "Good luck on track! 🏁"
    )


# ─────────────────────────────────────────────
# IMPROVED /help
# ─────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    args = message.text.strip().split(maxsplit=1)
    topic = args[1].lower().strip() if len(args) > 1 else None

    if topic == "team":
        text = (
            "🏎️ <b>Team Commands</b>\n\n"
            "/register — Create your F1 team\n"
            "/team — View full team overview\n"
            "/upgrade — Upgrade car stats (costs money)\n"
            "/renameteam — Change your team name\n"
            "/deleteteam — Permanently delete your team\n"
            "/budget — Full budget breakdown\n\n"
            "<i>Tip: Upgrade Engine + Aero first for the biggest race impact.</i>"
        )
    elif topic == "race":
        text = (
            "🏁 <b>Race Commands</b>\n\n"
            "/strategy — Set tyre compound + stop strategy\n"
            "/practice — Get a circuit preview + weather forecast\n"
            "/nextrace — See when the next race is\n"
            "/mycalendar — Full season schedule\n"
            "/predict — Predict the next race podium\n"
            "/runrace — Trigger next race (league owner only)\n\n"
            "<i>Tip: Always check /practice before setting strategy — weather changes everything.</i>"
        )
    elif topic == "drivers":
        text = (
            "👤 <b>Driver Commands</b>\n\n"
            "/market — Open the driver market\n"
            "/buydriver &lt;id&gt; — Sign a free agent\n"
            "/selldriver &lt;id&gt; [price] — List driver for transfer\n"
            "/bid &lt;listing_id&gt; &lt;amount&gt; — Bid on a listed driver\n"
            "/search &lt;name&gt; — Search drivers by name\n\n"
            "<i>Tip: You can have max 2 drivers. Sell one before signing another.</i>"
        )
    elif topic == "league":
        text = (
            "🏆 <b>League Commands</b>\n\n"
            "/league — View your league / create or join one\n"
            "/startseason — Start the season (league owner)\n"
            "/runrace — Run the next race (league owner)\n"
            "/standings — Driver + Constructor standings\n"
            "/setgroup — Link a Telegram group (run inside group, owner only)\n"
            "/unsetgroup — Unlink the group\n"
            "/leaveleague — Leave your current league\n"
            "/deleteleague — Delete league (owner only)\n\n"
            "<i>Tip: You need at least 2 teams before starting a season.</i>"
        )
    elif topic == "staff":
        text = (
            "👷 <b>Staff Commands</b>\n\n"
            "/staffmarket — Browse available staff\n"
            "/hirestaff &lt;id&gt; — Hire a staff member\n"
            "/mystaff — View your current staff\n"
            "/firestaff &lt;contract_id&gt; — Release a staff member\n\n"
            "<i>Tip: Technical Director + Head of Strategy give the biggest race bonuses.</i>"
        )
    elif topic == "stats":
        text = (
            "📊 <b>Stats & Social Commands</b>\n\n"
            "/profile — Your full career stats + achievements\n"
            "/halloffame — All-time top teams + season champions\n"
            "/h2h &lt;@user&gt; — Head to head record vs another team\n"
            "/standings — Current season standings\n\n"
        )
    else:
        text = (
            "📖 <b>F1 Racing Manager — Help</b>\n\n"
            "Choose a topic for detailed info:\n\n"
            "  /help team — Team management\n"
            "  /help race — Race weekend & strategy\n"
            "  /help drivers — Signing & transfers\n"
            "  /help league — Leagues & seasons\n"
            "  /help staff — Staff market\n"
            "  /help stats — Profile & standings\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 <b>Quick Start</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "/tutorial — Step-by-step guide for new managers\n"
            "/register — Create your team\n"
            "/market — Sign drivers\n"
            "/league — Join a league\n"
            "/daily — Claim daily reward\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>Stats</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "/profile — Your career stats\n"
            "/halloffame — All-time records\n"
            "/h2h @user — Head to head\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🆕 <b>New</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "/predict — Pick the next race podium\n"
            "/mycalendar — Full season schedule\n"
            "/setgroup — Link race broadcasts to a group\n\n"
            "<i>Built by @amanception</i>"
        )

    await message.answer(text)


# ─────────────────────────────────────────────
# INLINE SEARCH  — /search <name>
# ─────────────────────────────────────────────

@router.message(Command("search"))
async def cmd_search(message: Message):
    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2 or len(args[1].strip()) < 2:
        await message.answer(
            "🔍 <b>Search</b>\n\n"
            "Usage: <code>/search &lt;name&gt;</code>\n"
            "Example: <code>/search Hamilton</code>\n\n"
            "Searches both drivers and staff."
        )
        return

    query = args[1].strip().lower()

    async with get_session() as db:
        from sqlalchemy import or_

        # Search drivers
        drivers_res = await db.execute(
            select(Driver).where(
                Driver.name.ilike(f"%{query}%")
            ).limit(8)
        )
        drivers = drivers_res.scalars().all()

        # Search staff
        staff_res = await db.execute(
            select(Staff).where(
                Staff.name.ilike(f"%{query}%")
            ).limit(5)
        )
        staff = staff_res.scalars().all()

    if not drivers and not staff:
        await message.answer(f"❌ No results found for <b>{safe(query)}</b>.")
        return

    text = f"🔍 <b>Search: \"{safe(args[1].strip())}\"</b>\n\n"

    if drivers:
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "👤 <b>Drivers</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        for d in drivers:
            avg = (d.pace + d.racecraft + d.consistency + d.overtaking) // 4
            status = "🆓 Free Agent" if d.is_free_agent else "🔒 Contracted"
            text += (
                f"\n<b>{safe(d.name)}</b> #{d.number or '—'} | {safe(d.nationality)}\n"
                f"  Rating: {avg}/100 | Age: {d.age} | {status}\n"
                f"  Salary: ${d.base_salary:,}/yr\n"
                f"  ID: <code>{d.id}</code> → /buydriver {d.id}\n"
            )

    if staff:
        text += "\n━━━━━━━━━━━━━━━━━━━━\n"
        text += "👷 <b>Staff</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        for s in staff:
            status = "🆓 Available" if s.is_available else "🔒 Hired"
            text += (
                f"\n<b>{safe(s.name)}</b> | {safe(s.role.value.replace('_', ' ').title())}\n"
                f"  Bonus: +{int((s.performance_bonus - 1) * 100)}% | {status}\n"
                f"  Salary: ${s.salary:,}/yr\n"
                f"  ID: <code>{s.id}</code> → /hirestaff {s.id}\n"
            )

    await message.answer(text)
