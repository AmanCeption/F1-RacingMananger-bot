"""
Notification Service
Handles: Race Reminders, Transfer Alerts, Daily Reward Reminders
"""
import logging
from aiogram import Bot
from aiogram.types import BufferedInputFile
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
from src.services.circuit_images import get_circuit_image_url
from src.services.standings_image import generate_race_standings_image
from src.models.models import (
    User, Team, League, Race, RaceStatus, LeagueStatus,
    TeamDriver, Driver, DriverTransfer, TransferStatus
)

logger = logging.getLogger(__name__)


async def safe_send(bot: Bot, user_id: int, text: str) -> bool:
    """Send a message safely — silently skip if user blocked the bot."""
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
        return True
    except TelegramForbiddenError:
        logger.debug(f"User {user_id} has blocked the bot — skipping notification.")
    except TelegramBadRequest as e:
        logger.debug(f"Bad request for user {user_id}: {e}")
    except Exception as e:
        logger.warning(f"Failed to notify user {user_id}: {e}")
    return False


async def safe_send_photo(bot: Bot, user_id: int, photo_url: str, caption: str) -> bool:
    """Send a photo with caption safely. Falls back to text-only if photo fails."""
    try:
        await bot.send_photo(user_id, photo=photo_url, caption=caption, parse_mode="HTML")
        return True
    except TelegramForbiddenError:
        logger.debug(f"User {user_id} has blocked the bot — skipping.")
    except TelegramBadRequest as e:
        logger.debug(f"Photo send failed for user {user_id}: {e} — falling back to text.")
        return await safe_send(bot, user_id, caption)
    except Exception as e:
        logger.warning(f"Photo send failed for {user_id}: {e} — falling back to text.")
        return await safe_send(bot, user_id, caption)
    return False


# ─────────────────────────────────────────────
# RACE REMINDER  (1 hour before)
# ─────────────────────────────────────────────

async def send_race_reminders(bot: Bot):
    """
    DM every player in an active league that a race is coming up in ~1 hour.
    Called by the scheduler 1 hour before the scheduled race time.
    """
    logger.info("Sending race reminders...")
    sent = 0

    async with get_session() as db:
        # All active leagues with a scheduled next race
        leagues_res = await db.execute(
            select(League).where(League.status == LeagueStatus.ACTIVE)
        )
        leagues = leagues_res.scalars().all()

        for league in leagues:
            # Find next scheduled race
            race_res = await db.execute(
                select(Race).where(
                    and_(Race.league_id == league.id, Race.status == RaceStatus.SCHEDULED)
                ).order_by(Race.round.asc()).limit(1)
            )
            race = race_res.scalar_one_or_none()
            if not race:
                continue

            # Get all teams in this league
            teams_res = await db.execute(
                select(Team).where(Team.league_id == league.id)
            )
            teams = teams_res.scalars().all()

            for team in teams:
                user_res = await db.execute(select(User).where(User.id == team.owner_id))
                user = user_res.scalar_one_or_none()
                if not user or user.is_banned:
                    continue

                text = (
                    f"🏁 <b>Race Reminder — {league.name}</b>\n\n"
                    f"Round {race.round}: <b>{race.circuit}</b> starts in about 1 hour!\n\n"
                    f"🛞 Set your tyre strategy: /strategy\n"
                    f"🔧 Check your car setup: /practice\n\n"
                    f"Good luck on track! 🏎️"
                )
                image_url = await get_circuit_image_url(race.circuit_name or race.circuit)
                if await safe_send_photo(bot, user.id, image_url, text):
                    sent += 1

    logger.info(f"Race reminders sent to {sent} players.")


# ─────────────────────────────────────────────
# TRANSFER ALERT
# ─────────────────────────────────────────────

async def send_transfer_alert(bot: Bot, db: AsyncSession, transfer_id: int, bidder_team_name: str, bid_amount: int):
    """
    Alert the selling team owner when someone places a bid on their driver.
    Call this right after a bid is placed.
    """
    transfer_res = await db.execute(
        select(DriverTransfer, Driver)
        .join(Driver, DriverTransfer.driver_id == Driver.id)
        .where(DriverTransfer.id == transfer_id)
    )
    row = transfer_res.first()
    if not row:
        return

    transfer, driver = row

    if not transfer.selling_team_id:
        return

    # Get selling team owner
    team_res = await db.execute(select(Team).where(Team.id == transfer.selling_team_id))
    team = team_res.scalar_one_or_none()
    if not team:
        return

    user_res = await db.execute(select(User).where(User.id == team.owner_id))
    user = user_res.scalar_one_or_none()
    if not user or user.is_banned:
        return

    text = (
        f"💸 <b>New Bid on {driver.name}!</b>\n\n"
        f"<b>{bidder_team_name}</b> has placed a bid of <b>${bid_amount:,}</b> "
        f"on your driver <b>{driver.name}</b>.\n\n"
        f"Check the transfer market: /market"
    )
    await safe_send(bot, user.id, text)


async def send_outbid_alert(bot: Bot, db: AsyncSession, transfer_id: int, outbid_team_id: int, new_bid: int):
    """
    Alert a team that they've been outbid on a driver they were leading on.
    """
    transfer_res = await db.execute(
        select(DriverTransfer, Driver)
        .join(Driver, DriverTransfer.driver_id == Driver.id)
        .where(DriverTransfer.id == transfer_id)
    )
    row = transfer_res.first()
    if not row:
        return
    transfer, driver = row

    team_res = await db.execute(select(Team).where(Team.id == outbid_team_id))
    team = team_res.scalar_one_or_none()
    if not team:
        return

    user_res = await db.execute(select(User).where(User.id == team.owner_id))
    user = user_res.scalar_one_or_none()
    if not user or user.is_banned:
        return

    text = (
        f"⚠️ <b>You've been outbid!</b>\n\n"
        f"Someone placed <b>${new_bid:,}</b> on <b>{driver.name}</b> — "
        f"you're no longer the highest bidder.\n\n"
        f"Raise your bid: /market"
    )
    await safe_send(bot, user.id, text)


# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# RACE RESULTS  (after auto-race runs)
# ─────────────────────────────────────────────

async def send_race_results(bot: Bot, league_id: int, race_result: dict):
    """
    DM every team owner in the league with the race results summary.
    Call this from auto_run_races() right after run_race() returns.
    """
    logger.info(f"Sending race results for league {league_id}")
    sent = 0

    weather_emojis = {
        "sunny": "☀️", "cloudy": "🌥️",
        "light_rain": "🌧️", "heavy_rain": "⛈️", "mixed": "🌦️",
    }
    weather_label = weather_emojis.get(race_result.get("weather", ""), "🌤️")

    # ── Normalise results: CarEntry objects → dicts ──────────────────────
    # race_engine returns CarEntry dataclass objects, not dicts
    raw_results = race_result.get("results", [])
    F1_POINTS = {1:25,2:18,3:15,4:12,5:10,6:8,7:6,8:4,9:2,10:1}

    normalised = []
    for r in raw_results:
        if hasattr(r, "team_name"):  # CarEntry object
            pos  = r.position
            pts  = F1_POINTS.get(pos, 0) if not r.is_dnf else 0
            normalised.append({
                "position":    pos,
                "team":        r.team_name,
                "driver":      r.driver_name,
                "points":      pts,
                "total_points": 0,   # filled below from DB
                "dnf":         r.is_dnf,
                "dnf_reason":  r.dnf_reason,
                "fastest_lap": r.has_fastest_lap,
                "team_id":     r.team_id,
            })
        else:  # already a dict (future-proof)
            normalised.append(r)

    # ── Fetch total championship points from DB ──────────────────────────
    async with get_session() as pts_db:
        from src.models.models import ConstructorStanding
        cs_res = await pts_db.execute(
            select(ConstructorStanding).where(ConstructorStanding.league_id == league_id)
        )
        cs_rows = {row.team_id: row.points for row in cs_res.scalars().all()}
    for r in normalised:
        r["total_points"] = cs_rows.get(r.get("team_id"), r.get("points", 0))

    lines = []
    for r in normalised[:5]:
        if r["dnf"]:
            lines.append(f"  💥 DNF — {r['driver']} ({r['team']})")
        else:
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r["position"], f"  P{r['position']}")
            fl = " ⚡" if r.get("fastest_lap") else ""
            lines.append(f"  {medal} {r['driver']} ({r['team']}) +{r['points']}pts{fl}")

    top5_text = "\n".join(lines) if lines else "  No results available."

    # ── Generate standings image ONCE for the whole league ──────────────
    standings_img_bytes: bytes | None = None
    try:
        standings_img_bytes = generate_race_standings_image(
            race_name=race_result.get("race_name", "Race"),
            circuit=race_result.get("circuit", ""),
            weather_label=weather_label,
            results=normalised,
        )
        logger.info(f"Standings image generated: {len(standings_img_bytes)} bytes")
    except Exception as e:
        logger.warning(f"Standings image generation failed: {e}", exc_info=True)

    standings_file = (
        BufferedInputFile(standings_img_bytes, filename="standings.png")
        if standings_img_bytes else None
    )

    async with get_session() as db:
        teams_res = await db.execute(
            select(Team).where(Team.league_id == league_id)
        )
        teams = teams_res.scalars().all()

        for team in teams:
            user_res = await db.execute(select(User).where(User.id == team.owner_id))
            user = user_res.scalar_one_or_none()
            if not user or user.is_banned:
                continue

            team_result = next(
                (r for r in normalised if r["team"] == team.name),
                None,
            )
            if team_result:
                if team_result["dnf"]:
                    personal = f"\n\n🔧 <b>Your result:</b> DNF — {team_result.get('dnf_reason') or 'mechanical failure'}"
                else:
                    personal = (
                        f"\n\n🏎️ <b>Your result:</b> P{team_result['position']} "
                        f"— {team_result['points']} pts"
                        + (" ⚡ Fastest lap!" if team_result.get("fastest_lap") else "")
                    )
            else:
                personal = ""

            insight_text = ""
            insight = race_result.get("staff_insights", {}).get(team.id)
            if insight:
                insight_text = f"\n\n💬 <i>{insight[:200]}</i>"

            caption = (
                f"🏁 <b>{race_result['race_name']}</b> — Finished!\n"
                f"{weather_label} {race_result.get('circuit', '')}\n\n"
                f"<b>Race Results:</b>\n{top5_text}"
                f"{personal}"
                f"{insight_text}\n\n"
                f"📊 Season standings: /standings"
            )

            try:
                if standings_file:
                    # Re-wrap bytes each time (Telegram requires fresh file per send)
                    file_to_send = BufferedInputFile(standings_img_bytes, filename="standings.png")
                    await bot.send_photo(user.id, photo=file_to_send, caption=caption, parse_mode="HTML")
                else:
                    await safe_send(bot, user.id, caption)
                sent += 1
            except TelegramForbiddenError:
                pass
            except Exception as e:
                logger.warning(f"Failed to send results to {user.id}: {e}")
                await safe_send(bot, user.id, caption)

    logger.info(f"Race results sent to {sent} players in league {league_id}.")


# ─────────────────────────────────────────────
# SEASON END ANNOUNCEMENT
# ─────────────────────────────────────────────

async def send_season_end_announcement(bot: Bot, league_id: int, season_summary: dict):
    """
    Send a rich season-end announcement to all players in the league.
    Called from scheduler/auto_run_races when _end_season triggers.
    """
    logger.info(f"Sending season end announcement for league {league_id}, season {season_summary.get('season')}")

    season_num      = season_summary.get("season", "?")
    league_name     = season_summary.get("league_name", "League")
    cons_champ      = season_summary.get("constructor_champion_name", "TBD")
    cons_pts        = season_summary.get("constructor_champion_points", 0)
    drv_champ       = season_summary.get("driver_champion_name", "TBD")
    drv_pts         = season_summary.get("driver_champion_points", 0)
    drv_team        = season_summary.get("driver_champion_team_name", "")

    announcement = (
        f"🏆 <b>SEASON {season_num} — CHAMPIONSHIP OVER!</b>\n"
        f"🏟️ <i>{league_name}</i>\n"
        f"{'═' * 28}\n\n"
        f"👑 <b>DRIVERS' CHAMPION</b>\n"
        f"  🏎️ <b>{drv_champ}</b> ({drv_team})\n"
        f"  📊 {drv_pts} points\n\n"
        f"🏗️ <b>CONSTRUCTORS' CHAMPION</b>\n"
        f"  🏢 <b>{cons_champ}</b>\n"
        f"  📊 {cons_pts} points\n"
        f"  💰 Prize: <b>$100,000,000</b> awarded!\n\n"
        f"{'─' * 28}\n"
        f"🌅 <b>Season {season_num + 1} is coming!</b>\n"
        f"Drivers age, young stars develop, and the grid resets.\n"
        f"Use /league to check when the new season starts.\n\n"
        f"🔬 Spend your Research Points: /research\n"
        f"🏪 Check the driver market: /drivermarket"
    )

    async with get_session() as db:
        teams_res = await db.execute(select(Team).where(Team.league_id == league_id))
        teams = teams_res.scalars().all()

        sent = 0
        for team in teams:
            user_res = await db.execute(select(User).where(User.id == team.owner_id))
            user = user_res.scalar_one_or_none()
            if not user or user.is_banned:
                continue

            # Personalised ending line
            is_cons_champ = team.name == cons_champ
            personal = ""
            if is_cons_champ:
                personal = f"\n\n🎉 <b>Congratulations! Your team is the Constructor Champion!</b>"

            try:
                await safe_send(bot, user.id, announcement + personal)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send season end to {user.id}: {e}")

    logger.info(f"Season end announcement sent to {sent} players in league {league_id}.")

# DAILY REWARD REMINDER
# ─────────────────────────────────────────────

async def send_daily_reminders(bot: Bot):
    """
    DM players who haven't claimed their daily reward in 23+ hours.
    Runs once a day via scheduler.
    """
    from datetime import datetime, timedelta
    logger.info("Sending daily reward reminders...")
    sent = 0

    async with get_session() as db:
        users_res = await db.execute(select(User).where(User.is_banned == False))
        users = users_res.scalars().all()

        now = datetime.utcnow()
        for user in users:
            # Only remind if: never claimed, or last claim was 23+ hours ago (not yet 24h)
            if user.last_daily is None:
                eligible = True
            else:
                hours_since = (now - user.last_daily).total_seconds() / 3600
                eligible = hours_since >= 23

            if not eligible:
                continue

            # Only remind users who have a team (they're active players)
            team_res = await db.execute(select(Team).where(Team.owner_id == user.id))
            team = team_res.scalar_one_or_none()
            if not team:
                continue

            text = (
                f"🎁 <b>Daily Reward Ready!</b>\n\n"
                f"Hey {user.first_name}, your daily reward is waiting for you.\n"
                f"Claim it now to get money + research points.\n\n"
                f"👉 /daily"
            )
            if await safe_send(bot, user.id, text):
                sent += 1

    logger.info(f"Daily reminders sent to {sent} players.")
