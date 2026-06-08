"""
Logging Middleware
"""
import logging
import time
from typing import Callable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: dict) -> Any:
        start = time.time()

        user_id = None
        text = ""
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            text = event.text or ""
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            text = f"[callback] {event.data}"

        try:
            result = await handler(event, data)
            elapsed = (time.time() - start) * 1000
            logger.debug(f"User {user_id} | {text[:50]} | {elapsed:.1f}ms")
            return result
        except Exception as e:
            logger.error(f"Error for user {user_id} | {text[:50]}: {e}", exc_info=True)
            raise
