"""
Authentication Middleware
"""
from typing import Callable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from src.core.database.session import get_session
from src.services.game_services import UserService


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: dict) -> Any:
        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user:
            async with get_session() as db:
                svc = UserService(db)
                db_user = await svc.get_or_create(user.id, user.username, user.first_name)

                if db_user.is_banned:
                    if isinstance(event, Message):
                        await event.answer(
                            f"🚫 You are banned.\nReason: {db_user.ban_reason or 'No reason given'}"
                        )
                    return

                data["db_user"] = db_user

        return await handler(event, data)
