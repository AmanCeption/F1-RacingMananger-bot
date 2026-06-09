"""
Scheduler - Race automation, weekly RP grants, notifications
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from sqlalchemy import select

from src.core.database.session import get_session
from src.core.config import settings
from src.models.models import League, Team, LeagueStatus
from src.services.game_services import RaceService
from src.services.notification_service import send_race_reminders, send_daily_reminders

logger = logging.getLogger(__name__)


async def auto_run_races(bot: Bot):
    """Auto-trigger race for all active leagues"""
    logger.info("Auto-race scheduler triggered")
    async with get_session() as db:
        result = await db.execute(
            select(League).where(League.status == LeagueStatus.ACTIVE)
        )
        leagues = result.scalars().all()

        for league in leagues:
            try:
                svc = RaceService(db)
                race_result = await svc.run_race(league.id)
                if race_result:
                    events = race_result["events"][:15]
                    msg = "\n".join(events)
                    logger.info(f"Race completed for league {league.id}")
            except Exception as e:
                logger.error(f"Race failed for league {league.id}: {e}")


async def weekly_research_points(bot: Bot):
    """Grant weekly RP to all teams"""
    logger.info("Granting weekly research points")
    async with get_session() as db:
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        for team in teams:
            bonus = team.wind_tunnel_level * 5 + team.simulator_level * 5
            team.research_points += settings.WEEKLY_RESEARCH_POINTS + bonus
        await db.commit()
        logger.info(f"RP granted to {len(teams)} teams")


async def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    # ── Race (Sunday at RACE_HOUR:RACE_MINUTE UTC) ──
    scheduler.add_job(
        auto_run_races,
        CronTrigger(
            day_of_week="sun",
            hour=settings.RACE_HOUR,
            minute=settings.RACE_MINUTE,
        ),
        args=[bot],
        id="auto_race",
        replace_existing=True,
    )

    # ── Race Reminder (1 hour before race) ──
    reminder_hour = settings.RACE_HOUR - 1 if settings.RACE_HOUR > 0 else 23
    reminder_day = "sun" if settings.RACE_HOUR > 0 else "sat"
    scheduler.add_job(
        send_race_reminders,
        CronTrigger(
            day_of_week=reminder_day,
            hour=reminder_hour,
            minute=settings.RACE_MINUTE,
        ),
        args=[bot],
        id="race_reminder",
        replace_existing=True,
    )

    # ── Weekly RP (Monday 00:00 UTC) ──
    scheduler.add_job(
        weekly_research_points,
        CronTrigger(day_of_week="mon", hour=0, minute=0),
        args=[bot],
        id="weekly_rp",
        replace_existing=True,
    )

    # ── Daily Reward Reminder (every day at 10:00 UTC) ──
    scheduler.add_job(
        send_daily_reminders,
        CronTrigger(hour=10, minute=0),
        args=[bot],
        id="daily_reminder",
        replace_existing=True,
    )

    return scheduler
