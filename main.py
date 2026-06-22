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
from src.core.database.session import create_db_and_tables, engine, AsyncSessionLocal
from src.services.game_services import seed_database
from src.core.scheduler import setup_scheduler
from src.bot.handlers import register_all_handlers
from src.bot.middleware.auth import AuthMiddleware
from src.bot.middleware.anti_cheat import AntiCheatMiddleware
from src.bot.middleware.logging import LoggingMiddleware
from src.utils.logger import setup_logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


# ── Auto Migration (safe — IF NOT EXISTS) ───
async def run_migrations():
    """Runs safe ALTER TABLE migrations on every startup. IF NOT EXISTS = no harm if already done."""
    # PostgreSQL: ALTER TYPE ADD VALUE cannot run inside a transaction block.
    # Must use AUTOCOMMIT isolation level in a raw connection.
    staff_role_values = [
        "team_principal", "technical_director", "chief_designer",
        "head_of_aerodynamics", "aerodynamicist", "race_engineer",
        "chief_race_engineer", "pit_crew_chief", "sporting_director",
        "power_unit_director", "head_of_strategy", "performance_director",
    ]
    try:
        async with engine.connect() as raw_conn:
            await raw_conn.execution_options(isolation_level="AUTOCOMMIT")
            for val in staff_role_values:
                try:
                    await raw_conn.execute(text(
                        f"ALTER TYPE staffrole ADD VALUE IF NOT EXISTS '{val}'"
                    ))
                except Exception:
                    pass  # value already exists or enum doesn't exist yet
        logger.info("✅ staffrole enum values ensured")
    except Exception as e:
        logger.warning(f"staffrole enum migration warning: {e}")

    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE staff ADD COLUMN IF NOT EXISTS is_real BOOLEAN DEFAULT FALSE"
            ))
            await conn.execute(text(
                "ALTER TABLE staff ADD COLUMN IF NOT EXISTS specialty VARCHAR(64)"
            ))

            # Add unique constraints on standings tables (safe — IF NOT EXISTS)
            for constraint_sql in [
                """
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_driver_standing'
                    ) THEN
                        ALTER TABLE driver_standings
                            ADD CONSTRAINT uq_driver_standing
                            UNIQUE (league_id, season, driver_id);
                    END IF;
                END $$;
                """,
                """
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_constructor_standing'
                    ) THEN
                        ALTER TABLE constructor_standings
                            ADD CONSTRAINT uq_constructor_standing
                            UNIQUE (league_id, season, team_id);
                    END IF;
                END $$;
                """,
            ]:
                try:
                    await conn.execute(text(constraint_sql))
                except Exception as e:
                    logger.warning(f"Standings constraint migration warning: {e}")
            # Fix cascade deletes for team-related tables
            cascade_tables = [
                "race_results", "race_strategies", "qualifying_results",
                "team_drivers", "team_staff", "team_sponsors",
                "research_projects", "team_achievements",
                "driver_standings", "constructor_standings",
            ]
            for table in cascade_tables:
                try:
                    await conn.execute(text(f"""
                        DO $$ BEGIN
                            ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_team_id_fkey;
                            ALTER TABLE {table} ADD CONSTRAINT {table}_team_id_fkey
                                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE;
                        END $$;
                    """))
                except Exception:
                    pass  # table may not exist yet

            # Fix races.league_id FK — allow NULL when league is deleted
            try:
                await conn.execute(text("""
                    DO $$ BEGIN
                        ALTER TABLE races DROP CONSTRAINT IF EXISTS races_league_id_fkey;
                        ALTER TABLE races ADD CONSTRAINT races_league_id_fkey
                            FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE SET NULL;
                    END $$;
                """))
                # Allow NULL in existing rows if any orphaned races exist
                await conn.execute(text("""
                    ALTER TABLE races ALTER COLUMN league_id DROP NOT NULL;
                """))
            except Exception as e:
                logger.warning(f"races FK migration warning: {e}")
        logger.info("✅ Migrations applied successfully")
    except Exception as e:
        logger.warning(f"Migration warning (non-fatal): {e}")


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

    await run_migrations()

    async with AsyncSessionLocal() as session:
        await seed_database(session)
    logger.info("Database seeded")

    scheduler = await setup_scheduler(bot)
    dp["scheduler"] = scheduler
    scheduler.start()
    logger.info("Scheduler started")

    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(3)  # Wait for old instance to fully stop
    logger.info("Bot started successfully!")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        handle_signals=False,  # Let Render handle SIGTERM cleanly
    )


# ── Run both together ────────────────────────
async def main():
    setup_logging()
    await asyncio.gather(
        run_web_server(),
        run_bot(),
    )


if __name__ == "__main__":
    asyncio.run(main())
