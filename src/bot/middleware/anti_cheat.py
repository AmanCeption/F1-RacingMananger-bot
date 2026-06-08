"""
Anti-Cheat Middleware
Prevents rate abuse, duplicate exploits
"""
import logging
from typing import Callable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from src.core.cache.redis_client import get_cache
from src.core.config import settings

logger = logging.getLogger(__name__)


class AntiCheatMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: dict) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        cache = await get_cache()

        # Rate limit: max commands per minute
        count = await cache.rate_limit(user_id)
        if count > settings.MAX_COMMANDS_PER_MINUTE:
            if count == settings.MAX_COMMANDS_PER_MINUTE + 1:
                # Log suspicious activity once
                logger.warning(f"Rate limit hit: user {user_id} sent {count} commands/min")
                await event.answer(
                    "⚠️ Slow down! You're sending commands too fast. Please wait a moment.",
                    show_alert=True
                )
            return

        # Global command cooldown
        cooldown = await cache.get_cooldown(user_id, "global")
        if cooldown:
            return  # silently ignore during cooldown

        await cache.set_cooldown(user_id, "global", settings.COMMAND_COOLDOWN)

        return await handler(event, data)
