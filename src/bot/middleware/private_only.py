"""
PrivateOnlyMiddleware
─────────────────────
Blocks personal/state-changing commands when used in group chats.
Instead of silently ignoring or spamming the group, the bot:
  1. Deletes the command message from the group (if it has delete_message permission)
  2. Sends the user a private DM explaining they need to use the bot in DM
  3. Posts a brief, non-spammy reply in the group (only once per user per 60s)

Group-safe commands (public info, allowed in groups):
  /start, /help, /standings, /nextrace, /halloffame, /h2h, /search, /profile
  — everything else is DM-only.
"""

import time
import logging
from typing import Callable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, ChatType

logger = logging.getLogger(__name__)

# ── Commands that ARE allowed in groups ─────────────────────────────────────
GROUP_ALLOWED_COMMANDS = {
    # Public info
    "start", "help", "standings", "nextrace",
    "halloffame", "h2h", "search", "profile",
    # Race Weekend — allowed in groups
    "practice", "qualifying", "strategy", "runrace", "sprintrace", "startseason",
    # Onboarding — allowed in groups
    "tutorial",
}

# ── Throttle: only notify group once per user per N seconds ─────────────────
_last_group_notify: dict[int, float] = {}
GROUP_NOTIFY_COOLDOWN = 60   # seconds


class PrivateOnlyMiddleware(BaseMiddleware):
    """Intercepts group messages and redirects personal commands to DM."""

    async def __call__(
        self,
        handler: Callable,
        event: TelegramObject,
        data: dict,
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        # Only care about group / supergroup chats
        chat_type = event.chat.type if event.chat else None
        if chat_type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await handler(event, data)

        # Only intercept actual bot commands (text starting with /)
        text = event.text or ""
        if not text.startswith("/"):
            return await handler(event, data)

        # Extract command name (strip / and @botname)
        raw_cmd = text.lstrip("/").split("@")[0].split()[0].lower()

        # If it's a group-allowed command, let it through
        if raw_cmd in GROUP_ALLOWED_COMMANDS:
            return await handler(event, data)

        # ── It's a DM-only command used in a group ───────────────────────
        user = event.from_user
        if not user:
            return  # ignore anonymous messages

        user_id   = user.id
        user_name = user.first_name or user.username or "there"
        now       = time.time()

        # 1. Try to delete the command from the group (keep chat clean)
        try:
            await event.delete()
        except Exception:
            pass  # no delete permission — that's fine

        # 2. Try to send the user a private DM
        bot = event.bot
        dm_sent = False
        try:
            await bot.send_message(
                user_id,
                f"👋 Hey <b>{user_name}</b>!\n\n"
                f"The command <code>/{raw_cmd}</code> is a personal command "
                f"and only works here in our private chat — not in groups.\n\n"
                f"Please use all team management, race, upgrade, and strategy "
                f"commands here in DM with me. Group chats are only for:\n"
                f"  • /standings — Championship table\n"
                f"  • /nextrace — Next race info\n"
                f"  • /help — Command list\n\n"
                f"<i>Come chat with me here anytime! 🏎️</i>",
                parse_mode="HTML",
            )
            dm_sent = True
        except Exception:
            # User may have never started the bot — can't DM them
            dm_sent = False

        # 3. Post a brief group notice (throttled — once per 60s per user)
        last_notify = _last_group_notify.get(user_id, 0)
        if now - last_notify > GROUP_NOTIFY_COOLDOWN:
            _last_group_notify[user_id] = now
            if dm_sent:
                notice = (
                    f"👤 {user_name}, personal commands work in "
                    f"<a href='https://t.me/{(await bot.get_me()).username}'>bot DM</a> only. "
                    f"I've sent you a message there! 📩"
                )
            else:
                notice = (
                    f"👤 {user_name}, please open "
                    f"<a href='https://t.me/{(await bot.get_me()).username}'>my DM</a> "
                    f"and use <code>/start</code> first, then try again here."
                )
            try:
                sent = await event.answer(notice, parse_mode="HTML")
                # Auto-delete the notice after 8 seconds to keep group clean
                import asyncio
                asyncio.create_task(_auto_delete(sent, delay=8))
            except Exception as e:
                logger.debug(f"Could not post group notice: {e}")

        # Do NOT call the handler — command is blocked in group
        return


async def _auto_delete(msg: Message, delay: int = 8) -> None:
    """Delete a message after `delay` seconds (best-effort)."""
    import asyncio
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass
