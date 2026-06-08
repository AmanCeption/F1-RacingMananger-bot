"""
Handler Registration
"""
from aiogram import Dispatcher
from src.bot.handlers.main_handlers import router as main_router
from src.bot.handlers.admin_handlers import router as admin_router


def register_all_handlers(dp: Dispatcher):
    dp.include_router(main_router)
    dp.include_router(admin_router)
