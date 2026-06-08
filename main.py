"""
F1 Management Bot - Render Web Service compatible
Runs bot + dummy HTTP server together
"""
import asyncio
import logging
from aiohttp import web

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


# ── Dummy HTTP server (Render ke liye) ──────
async def health_check(request):
    return web.Response(text="F1 Bot is running! 🏎️")


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    logger.info("Health check server running on port 10000")


# ── Bot ─────────────────────────────────────
async def run_bot():
    storage = MemoryStorage()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=storage)

    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.message.middleware(AntiCheatMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    register_all_handlers(dp)

    logger.info("Starting F1 Management Bot...")
    await create_db_and_tables()
    logger.info("Database initialized")

    scheduler = await setup_scheduler(bot)
    dp["scheduler"] = scheduler
    scheduler.start()
    logger.info("Scheduler started")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started successfully!")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


# ── Run both together ────────────────────────
async def main():
    setup_logging()
    await asyncio.gather(
        run_web_server(),
        run_bot(),
    )


if __name__ == "__main__":
    asyncio.run(main())
