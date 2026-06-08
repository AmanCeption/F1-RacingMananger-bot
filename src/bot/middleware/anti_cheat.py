"""
Anti-Cheat Middleware - No Redis version
"""
import time
import logging
from typing import Callable, Any
from collections import defaultdict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

logger = logging.getLogger(__name__)

_rate_counts: dict = defaultdict(list)
_cooldowns: dict = {}

COMMAND_COOLDOWN = 3
MAX_COMMANDS_PER_MINUTE = 20


class AntiCheatMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: dict) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.time()

        minute_ago = now - 60
        _rate_counts[user_id] = [t for t in _rate_counts[user_id] if t > minute_ago]
        _rate_counts[user_id].append(now)

        if len(_rate_counts[user_id]) > MAX_COMMANDS_PER_MINUTE:
            await event.answer("⚠️ Too many commands! Please slow down.")
            return

        last = _cooldowns.get(user_id, 0)
        if now - last < COMMAND_COOLDOWN:
            return

        _cooldowns[user_id] = now
        return await handler(event, data)
