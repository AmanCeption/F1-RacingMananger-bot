"""
Notification Service
Handles: Race Reminders, Transfer Alerts, Daily Reward Reminders
"""
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import get_session
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
                if await safe_send(bot, user.id, text):
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

    lines = []
    for r in race_result.get("results", [])[:5]:
        if r["dnf"]:
            lines.append(f"  💥 DNF — {r['driver']} ({r['team']})")
        else:
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r["position"], f"  P{r['position']}")
            fl = " ⚡" if r.get("fastest_lap") else ""
            lines.append(f"  {medal} {r['driver']} ({r['team']}) +{r['points']}pts{fl}")

    top5_text = "\n".join(lines) if lines else "  No results available."

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
                (r for r in race_result.get("results", []) if r["team"] == team.name),
                None,
            )
            if team_result:
                if team_result["dnf"]:
                    personal = f"\n\n🔧 <b>Your result:</b> DNF — {team_result['dnf_reason'] or 'mechanical failure'}"
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

            text = (
                f"🏁 <b>{race_result['race_name']}</b> — Finished!\n"
                f"{weather_label} {race_result.get('circuit', '')}\n\n"
                f"<b>Top 5:</b>\n{top5_text}"
                f"{personal}"
                f"{insight_text}\n\n"
                f"📊 Full standings: /standings"
            )
            if await safe_send(bot, user.id, text):
                sent += 1

    logger.info(f"Race results sent to {sent} players in league {league_id}.")

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
