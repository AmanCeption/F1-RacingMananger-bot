"""
Admin Handlers — with live personalized race commentary
"""
import logging
import asyncio
import random
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.core.database.session import get_session
from src.core.config import settings
from src.services.game_services import AdminService, RaceService

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


# ─────────────────────────────────────────────
# COMMENTARY ENGINE
# ─────────────────────────────────────────────

def build_commentary(events: list, cars: list) -> list[str]:
    """
    Takes raw simulation events + CarEntry list.
    Returns a list of broadcast message strings (1 per message chunk).
    Each call produces different commentary — randomized templates.
    Total broadcast fits in ~1 minute.
    """

    # Gather names for personalization
    driver_names = [c["driver"] for c in cars if not c.get("dnf")]
    team_names   = [c["team"]   for c in cars if not c.get("dnf")]
    all_drivers  = [c["driver"] for c in cars]
    all_teams    = [c["team"]   for c in cars]

    def rd(lst):
        return random.choice(lst) if lst else "Unknown"

    # ── Template pools ────────────────────────────────────────────

    SC_LINES = [
        lambda lap: f"🟡 Lap {lap}: SAFETY CAR out on track! {rd(driver_names)} will be watching this closely.",
        lambda lap: f"🟡 Lap {lap}: Safety Car deployed — {rd(team_names)} immediately calls their driver in!",
        lambda lap: f"🟡 Lap {lap}: Caution period! {rd(driver_names)} radios: 'Safety car's out, what do we do?' Team replies: 'Stay out, stay out!'",
        lambda lap: f"🟡 Lap {lap}: SC on track — this could shake up the entire strategy for {rd(team_names)}!",
    ]

    GREEN_LINES = [
        lambda lap: f"🟢 Lap {lap}: GREEN FLAG! {rd(driver_names)} floors it immediately — no time to waste!",
        lambda lap: f"🟢 Lap {lap}: Safety Car in! {rd(driver_names)} already pushing — the restart is FRANTIC!",
        lambda lap: f"🟢 Lap {lap}: WE'RE RACING AGAIN! {rd(team_names)} pitwall erupts — let's GO!",
    ]

    VSC_LINES = [
        lambda lap: f"🟡 Lap {lap}: Virtual Safety Car! {rd(driver_names)} eases off — precious fuel saved.",
        lambda lap: f"🟡 Lap {lap}: VSC deployed. {rd(team_names)} engineers furiously recalculating strategy...",
    ]

    RED_FLAG_LINES = [
        lambda lap: f"🔴 Lap {lap}: RED FLAG! Race suspended! {rd(driver_names)} parks up on the formation lap.",
        lambda lap: f"🔴 Lap {lap}: RED FLAG! Chaos at the pitlane — {rd(team_names)} scrambles for a tyre change!",
    ]

    PIT_TEMPLATES = [
        lambda drv, old, new, err: f"🔧 {drv} dives into the pits — {old} → {new}! {rd(all_teams)} crew nails it!{err}",
        lambda drv, old, new, err: f"🔧 Box box box! {drv} responds immediately. Clean stop onto the {new}s.{err}",
        lambda drv, old, new, err: f"🔧 {drv} in for tyres — {old}s off, {new}s on.{' ⚠️ Bit slow!' if err else ' Lightning stop!'} ",
        lambda drv, old, new, err: f"🔧 {drv} pits! Radio: 'New {new}s are on.' — Back in P? Let's see where they come out!{err}",
    ]

    DNF_TEMPLATES = [
        lambda drv, team, rsn: f"💥 RETIREMENT! {drv} ({team}) is out of the race! {rsn}. Devastating for {team}.",
        lambda drv, team, rsn: f"💥 {drv} parks the car on the side of the track. {rsn} — race over for the {team} driver.",
        lambda drv, team, rsn: f"💥 OH NO! {drv} is out! {rsn}. {team} have lost their driver today.",
    ]

    OVT_TEMPLATES = [
        lambda a, d: f"⚡ MOVE OF THE RACE! {a} goes around the outside of {d} — BRILLIANT overtake!",
        lambda a, d: f"⚡ {a} dives up the inside of {d}! {d} tried to hold on but no chance!",
        lambda a, d: f"⚡ {a} makes his move on {d}! The crowd goes wild! What a battle!",
        lambda a, d: f"⚡ {a} vs {d} — and {a} takes the position! Incredible racing!",
        lambda a, d: f"⚡ {a} passes {d} with a slick DRS move down the straight!",
    ]

    HALFWAY_LINES = [
        lambda drv: f"🔄 Halfway through! {drv} leads the way. Can they hold on?",
        lambda drv: f"🔄 We're halfway! {drv} looking comfortable at the front, but anything can happen!",
        lambda drv: f"🔄 Mid-race! {drv} has been dominant so far. Opposition needs to respond!",
    ]

    FINAL_5_LINES = [
        lambda drv: f"⚡ 5 LAPS TO GO! {drv} holds the lead — can anyone stop them?",
        lambda drv: f"⚡ Final 5 laps! {drv} is so close to victory. Heart rate through the roof!",
        lambda drv: f"⚡ 5 laps remaining! {drv} on the radio: 'How long, how long?' Team: 'Five mate, five!'",
    ]

    WEATHER_LINES = [
        lambda w: f"🌦️ Conditions changing to {w}! Teams scrambling on strategy — this changes everything!",
        lambda w: f"🌦️ Weather update: {w} incoming! Some will gamble on tyres, some will stay out...",
    ]

    SLOW_PIT_ADDON = " ⚠️ SLOW STOP — that cost them dearly!"
    FAST_PIT_ADDON = ""

    # ── Parse events into structured commentary messages ──────────

    messages = []
    lap_buffer = []  # collect minor events before flushing

    def flush_buffer():
        if lap_buffer:
            messages.append("\n".join(lap_buffer))
            lap_buffer.clear()

    for ev in events:
        # Skip raw result lines — handled separately
        if any(ev.startswith(s) for s in ["🥇", "🥈", "🥉", "⚡ Fastest Lap", "\n🏆"]):
            continue
        if "RACE FINISHED" in ev:
            continue

        # ── Safety Car ─────────────────────────────────────────
        if "SAFETY CAR deployed" in ev or "SAFETY CAR out" in ev:
            lap = _extract_lap(ev)
            flush_buffer()
            messages.append(random.choice(SC_LINES)(lap))

        elif "Safety Car returning" in ev or "GREEN FLAG" in ev:
            lap = _extract_lap(ev)
            flush_buffer()
            messages.append(random.choice(GREEN_LINES)(lap))

        elif "VIRTUAL SAFETY CAR" in ev:
            lap = _extract_lap(ev)
            flush_buffer()
            messages.append(random.choice(VSC_LINES)(lap))

        # ── Red Flag ────────────────────────────────────────────
        elif "RED FLAG" in ev:
            lap = _extract_lap(ev)
            flush_buffer()
            messages.append(random.choice(RED_FLAG_LINES)(lap))

        # ── Pit Stop ────────────────────────────────────────────
        elif "pits —" in ev or "pits—" in ev:
            # Parse: "🔧 Lap 12: DriverName pits — Medium → Soft ⚠️ Slow pit stop!"
            flush_buffer()
            drv = _extract_between(ev, ": ", " pits")
            tyres = _extract_between(ev, "— ", None)
            old_t = tyres.split("→")[0].strip() if "→" in tyres else "old"
            new_t = tyres.split("→")[1].strip().split("⚠️")[0].strip() if "→" in tyres else "new"
            err = SLOW_PIT_ADDON if "Slow pit" in ev else FAST_PIT_ADDON
            template = random.choice(PIT_TEMPLATES)
            messages.append(template(drv, old_t, new_t, err))

        # ── DNF ─────────────────────────────────────────────────
        elif "RETIREMENT" in ev:
            flush_buffer()
            # "💥 Lap X: DriverName (TeamName) — RETIREMENT! Reason"
            drv = _extract_between(ev, ": ", " (")
            team = _extract_between(ev, "(", ")")
            reason = _extract_between(ev, "RETIREMENT! ", None) or "Mechanical failure"
            messages.append(random.choice(DNF_TEMPLATES)(drv, team, reason))

        # ── Overtake ────────────────────────────────────────────
        elif "overtakes" in ev:
            flush_buffer()
            # "⚡ Lap X: A overtakes B!"
            body = _extract_between(ev, ": ", None) or ev
            parts = body.replace("!", "").split(" overtakes ")
            if len(parts) == 2:
                messages.append(random.choice(OVT_TEMPLATES)(parts[0].strip(), parts[1].strip()))
            else:
                messages.append(f"⚡ {body}")

        # ── Halfway ─────────────────────────────────────────────
        elif "Halfway" in ev or "halfway" in ev:
            leader = driver_names[0] if driver_names else rd(all_drivers)
            flush_buffer()
            messages.append(random.choice(HALFWAY_LINES)(leader))

        # ── 5 Laps ──────────────────────────────────────────────
        elif "5 laps remaining" in ev:
            leader = driver_names[0] if driver_names else rd(all_drivers)
            flush_buffer()
            messages.append(random.choice(FINAL_5_LINES)(leader))

        # ── Weather change ───────────────────────────────────────
        elif "Weather changing" in ev:
            w = _extract_between(ev, "to ", "!") or "different conditions"
            flush_buffer()
            messages.append(random.choice(WEATHER_LINES)(w))

        # ── Race start lines ─────────────────────────────────────
        elif "Lights out" in ev or "Race STARTED" in ev:
            lap_buffer.append(f"🚦 {ev.replace('🚦 ', '')}")

        # ── Circuit banner (first event) ─────────────────────────
        elif "—" in ev and any(w in ev for w in ["Sunny", "Cloudy", "Rain", "Mixed"]):
            lap_buffer.append(f"🏁 {ev}")

        # ── Anything else (generic lap note) ────────────────────
        else:
            lap_buffer.append(ev)
            if len(lap_buffer) >= 2:
                flush_buffer()

    flush_buffer()
    return [m for m in messages if m.strip()]


def _extract_lap(ev: str) -> int:
    """Extract lap number from event string like 'Lap 12:'"""
    try:
        part = ev.split("Lap ")[1].split(":")[0]
        return int(part.strip())
    except Exception:
        return 0


def _extract_between(s: str, after: str, before) -> str:
    """Extract substring between two markers"""
    try:
        start = s.index(after) + len(after)
        if before is None:
            return s[start:].strip()
        end = s.index(before, start)
        return s[start:end].strip()
    except Exception:
        return ""


# ─────────────────────────────────────────────
# ADMIN COMMANDS
# ─────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🔧 <b>Admin Panel</b>\n\n"
        "/addmoney teamid amount\n"
        "/removemoney teamid amount\n"
        "/banplayer userid reason\n"
        "/unbanplayer userid\n"
        "/forcerace leagueid\n"
        "/broadcast &lt;message&gt; — sends to ALL users"
    )


@router.message(Command("addmoney"))
async def cmd_addmoney(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /addmoney teamid amount")
        return
    try:
        team_id, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Invalid values")
        return
    async with get_session() as db:
        result = await AdminService(db).add_money(message.from_user.id, team_id, amount)
        await message.answer(f"✅ Done: {result}")


@router.message(Command("removemoney"))
async def cmd_removemoney(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /removemoney teamid amount")
        return
    try:
        team_id, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Invalid values")
        return
    async with get_session() as db:
        result = await AdminService(db).add_money(message.from_user.id, team_id, -amount)
        await message.answer(f"✅ Done: {result}")


@router.message(Command("banplayer"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /banplayer userid reason")
        return
    try:
        user_id = int(parts[1])
        reason = parts[2]
    except ValueError:
        await message.answer("Invalid user_id")
        return
    async with get_session() as db:
        result = await AdminService(db).ban_player(message.from_user.id, user_id, reason)
        await message.answer(f"✅ Done: {result}")


@router.message(Command("unbanplayer"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /unbanplayer userid")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid user_id")
        return
    async with get_session() as db:
        result = await AdminService(db).unban_player(message.from_user.id, user_id)
        await message.answer(f"✅ Done: {result}")


@router.message(Command("forcerace"))
async def cmd_forcerace(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /forcerace leagueid\nExample: /forcerace 1")
        return
    try:
        league_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid league id")
        return

    await message.answer(f"⏳ Preparing race for league {league_id}...")

    try:
        async with get_session() as db:
            from sqlalchemy import select, and_
            from src.models.models import League, Race, Team, RaceStatus, LeagueStatus

            # Validations
            league_res = await db.execute(select(League).where(League.id == league_id))
            league = league_res.scalar_one_or_none()
            if not league:
                await message.answer(f"❌ League {league_id} not found!")
                return

            if league.status != LeagueStatus.ACTIVE:
                await message.answer(
                    f"❌ League not active! Status: <b>{league.status.value}</b>\n"
                    f"Run /startseason first."
                )
                return

            teams_res = await db.execute(select(Team).where(Team.league_id == league_id))
            teams = teams_res.scalars().all()
            if not teams:
                await message.answer("❌ No teams in this league!")
                return

            race_res = await db.execute(
                select(Race).where(
                    and_(Race.league_id == league_id, Race.status == RaceStatus.SCHEDULED)
                ).order_by(Race.round.asc()).limit(1)
            )
            next_race = race_res.scalar_one_or_none()
            if not next_race:
                await message.answer(
                    f"❌ No scheduled race for league {league_id}!\n"
                    f"All races finished. Check /standings."
                )
                return

            # Race start announcement
            await message.answer(
                f"🏁 <b>ROUND {next_race.round} — {next_race.name.upper()}</b>\n"
                f"🏟️ {next_race.circuit}\n"
                f"🔢 {next_race.laps} Laps | 👥 {len(teams)} Teams\n\n"
                f"🚦 Race starts in 5 seconds..."
            )
            await asyncio.sleep(5)

            # Run full simulation (instant)
            result = await RaceService(db).run_race(league_id)

            if not result:
                await message.answer("❌ Race simulation failed. Check logs.")
                return

            raw_events  = result.get("events", [])
            results_list = result.get("results", [])

            # Build personalized commentary — results_list is list of dicts
            race_cars = results_list
            commentary_chunks = build_commentary(raw_events, race_cars)

            # ── 1-MINUTE LIVE BROADCAST ──────────────────────────
            # Budget: ~60 seconds total across all messages
            # We spread delays evenly so total ≈ 60s
            total_msgs = len(commentary_chunks)
            if total_msgs == 0:
                await message.answer("Race completed!")
                return

            # Reserve ~8s for final results message
            broadcast_time = 52
            delay_per_msg = max(3, min(10, broadcast_time // max(total_msgs, 1)))

            # Opening message
            await message.answer(
                "🔴 <b>RACE IS LIVE!</b>\n\n" + (commentary_chunks[0] if commentary_chunks else "")
            )

            # Stream the rest
            for i, chunk in enumerate(commentary_chunks[1:], 1):
                await asyncio.sleep(delay_per_msg)
                is_drama = any(
                    kw in chunk for kw in
                    ["SAFETY CAR", "RED FLAG", "RETIREMENT", "overtakes", "VSC", "5 LAPS"]
                )
                prefix = "🚨 <b>INCIDENT</b>" if is_drama else "📡 <b>LIVE</b>"
                await message.answer(f"{prefix}\n\n{chunk}")

            # Chequered flag
            await asyncio.sleep(5)
            await message.answer("🏁 <b>CHEQUERED FLAG!</b>\n\nFinal results incoming...")
            await asyncio.sleep(3)

            # ── FINAL RESULTS ────────────────────────────────────
            medals = ["🥇", "🥈", "🥉"]
            podium_lines = []
            for idx, car in enumerate(results_list[:3]):
                if not car.get("dnf"):
                    gap = "WINNER ✨" if idx == 0 else ""
                    podium_lines.append(
                        f"{medals[idx]} <b>{car['driver']}</b> ({car['team']}) — {gap}"
                    )

            rest = [
                f"P{idx+4}. {car['driver']} ({car['team']})"
                for idx, car in enumerate(results_list[3:10])
                if not car.get("dnf")
            ]

            dnf_cars = [c for c in results_list if c.get("dnf")]
            dnf_text = ""
            if dnf_cars:
                dnf_text = "\n\n💥 <b>Retirements:</b>\n" + "\n".join(
                    f"  • {c['driver']} — {c.get('dnf_reason', 'Mechanical failure')}" for c in dnf_cars
                )

            fl_text = ""
            for car in results_list:
                if car.get("fastest_lap"):
                    fl_text = f"\n\n⚡ <b>Fastest Lap:</b> {car['driver']} 💜"
                    break

            weather_str = str(result.get("weather", "")).replace("_", " ").title()

            await message.answer(
                f"🏆 <b>RACE RESULT — {next_race.name}</b>\n"
                f"🌡️ {weather_str}\n\n"
                + "\n".join(podium_lines)
                + ("\n\n<b>Full Classification:</b>\n" + "\n".join(rest) if rest else "")
                + dnf_text
                + fl_text
                + "\n\n✅ Points & standings updated!"
            )

            # ── STAFF INSIGHTS — send to each team owner privately ──
            await asyncio.sleep(4)
            staff_insights = result.get("staff_insights", {})
            if staff_insights:
                # Get all team owners in this league
                from sqlalchemy import select as sa_select
                from src.models.models import Team as TeamModel
                async with get_session() as db2:
                    teams_res = await db2.execute(
                        sa_select(TeamModel).where(TeamModel.league_id == league_id)
                    )
                    all_teams = teams_res.scalars().all()
                for t in all_teams:
                    insight_text = staff_insights.get(t.id)
                    if insight_text and t.owner_id:
                        try:
                            await message.bot.send_message(
                                t.owner_id,
                                insight_text,
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass  # user may have blocked bot

    except Exception as e:
        logger.error(f"forcerace error: {e}", exc_info=True)
        await message.answer(f"❌ Error: <code>{str(e)}</code>")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    # Usage: /broadcast <message>
    # Supports full Telegram HTML: <b>, <i>, <code>, <a href="">, emoji, newlines
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "📡 <b>Broadcast Help</b>\n\n"
            "<b>Usage:</b> /broadcast &lt;message&gt;\n\n"
            "<b>Supports rich HTML:</b>\n"
            "  <code>&lt;b&gt;bold&lt;/b&gt;</code> → <b>bold</b>\n"
            "  <code>&lt;i&gt;italic&lt;/i&gt;</code> → <i>italic</i>\n"
            "  <code>&lt;code&gt;mono&lt;/code&gt;</code> → <code>mono</code>\n"
            "  Emoji ✅🏎️🔔 work natively\n\n"
            "<b>Examples:</b>\n"
            "  /broadcast 🔔 Server maintenance at 10PM tonight!\n"
            "  /broadcast &lt;b&gt;Season 2 starts Sunday!&lt;/b&gt; 🏁\n  Race at 14:00 UTC.",
            parse_mode="HTML"
        )
        return

    broadcast_text = parts[1]

    # ── Preview to admin before sending ──────────────────────────────────
    preview_header = (
        f"📢 <b>Announcement from F1 Bot</b>\n"
        f"{'─' * 30}\n\n"
        f"{broadcast_text}\n\n"
        f"<i>— F1 Management Bot Team</i>"
    )
    await message.answer(
        f"<b>👁️ Broadcast Preview:</b>\n{'─'*28}\n\n"
        + preview_header +
        f"\n\n{'─'*28}\n<i>Sending to all users now...</i>",
        parse_mode="HTML"
    )

    # Fetch all user IDs from DB
    async with get_session() as db:
        user_ids = await AdminService(db).get_all_user_ids()

    if not user_ids:
        await message.answer("❌ No users found in database.")
        return

    total = len(user_ids)
    sent = 0
    failed = 0

    status_msg = await message.answer(
        f"📡 Broadcasting to <b>{total}</b> users...\n"
        f"⏳ Please wait..."
    )

    # Full formatted broadcast message (HTML-rendered)
    full_text = preview_header

    for user_id in user_ids:
        try:
            await message.bot.send_message(user_id, full_text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        # Small delay to avoid Telegram rate limits (30 msgs/sec max)
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📨 Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b> (blocked/deleted bot)\n"
        f"👥 Total: <b>{total}</b>"
    )
