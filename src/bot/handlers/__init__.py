"""
Handler Registration
"""
from aiogram import Dispatcher
from src.bot.handlers.main_handlers import router as main_router
from src.bot.handlers.admin_handlers import router as admin_router
from src.bot.handlers.profile_handlers import router as profile_router
from src.bot.handlers.onboarding_handlers import router as onboarding_router


def register_all_handlers(dp: Dispatcher):
    dp.include_router(main_router)
    dp.include_router(admin_router)
    dp.include_router(profile_router)
    dp.include_router(onboarding_router)
