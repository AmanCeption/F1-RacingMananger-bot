"""
Admin Handlers
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from src.core.database.session import get_session
from src.core.config import settings
from src.services.game_services import AdminService, TeamService, RaceService

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🔧 <b>Admin Panel</b>\n\n"
        "/addmoney <team_id> <amount>\n"
        "/removemoney <team_id> <amount>\n"
        "/banplayer <user_id> <reason>\n"
        "/unbanplayer <user_id>\n"
        "/forcerace <league_id>\n"
        "/resetleague <league_id>\n"
        "/broadcast <message>"
    )


@router.message(Command("addmoney"))
async def cmd_addmoney(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /addmoney <team_id> <amount>")
        return
    try:
        team_id, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("❌ Invalid values")
        return
    async with get_session() as db:
        svc = AdminService(db)
        result = await svc.add_money(message.from_user.id, team_id, amount)
        await message.answer(f"✅ {result}")


@router.message(Command("removemoney"))
async def cmd_removemoney(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /removemoney <team_id> <amount>")
        return
    try:
        team_id, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("❌ Invalid values")
        return
    async with get_session() as db:
        svc = AdminService(db)
        result = await svc.add_money(message.from_user.id, team_id, -amount)
        await message.answer(f"✅ {result}")


@router.message(Command("banplayer"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /banplayer <user_id> <reason>")
        return
    try:
        user_id = int(parts[1])
        reason = parts[2]
    except ValueError:
        await message.answer("❌ Invalid user_id")
        return
    async with get_session() as db:
        result = await AdminService(db).ban_player(message.from_user.id, user_id, reason)
        await message.answer(f"✅ {result}")


@router.message(Command("unbanplayer"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /unbanplayer <user_id>")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid user_id")
        return
    async with get_session() as db:
        result = await AdminService(db).unban_player(message.from_user.id, user_id)
        await message.answer(f"✅ {result}")


@router.message(Command("forcerace"))
async def cmd_forcerace(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /forcerace <league_id>")
        return
    league_id = int(parts[1])
    await message.answer(f"⏳ Running race for league {league_id}...")
    async with get_session() as db:
        result = await RaceService(db).run_race(league_id)
        if result:
            events = result["events"][:10]
            summary = "\n".join(events)
            await message.answer(f"✅ Race complete!\n\n{summary}")
        else:
            await message.answer("❌ No race scheduled or failed.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /broadcast <message>")
        return
    await message.answer(f"📢 Broadcast sent:\n\n{parts[1]}")
