"""
F1 Management Game Bot - Main Entry Point
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.core.config import settings
from src.core.database.session import create_db_and_tables
from src.core.scheduler import setup_scheduler
from src.bot.handlers import register_all_handlers
from src.bot.middleware.auth import AuthMiddleware
from src.bot.middleware.anti_cheat import AntiCheatMiddleware
from src.bot.middleware.logging import LoggingMiddleware
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, dispatcher: Dispatcher):
    logger.info("Starting F1 Management Bot...")
    await create_db_and_tables()
    logger.info("Database initialized")

    scheduler = await setup_scheduler(bot)
    dispatcher["scheduler"] = scheduler
    scheduler.start()
    logger.info("Scheduler started")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started successfully!")


async def on_shutdown(bot: Bot, dispatcher: Dispatcher):
    logger.info("Shutting down bot...")
    scheduler = dispatcher.get("scheduler")
    if scheduler:
        scheduler.shutdown()
    await bot.session.close()


async def main():
    setup_logging()

    # Using MemoryStorage (no Redis needed - works on free Render)
    storage = MemoryStorage()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=storage)

    # Middleware
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.message.middleware(AntiCheatMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Handlers
    register_all_handlers(dp)

    # Hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
