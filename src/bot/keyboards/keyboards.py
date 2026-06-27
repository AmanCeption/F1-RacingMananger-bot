"""
Telegram Inline & Reply Keyboards
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🏎️ My Team"),
        KeyboardButton(text="🏁 Race"),
    )
    builder.row(
        KeyboardButton(text="🏆 Standings"),
        KeyboardButton(text="👥 League"),
    )
    builder.row(
        KeyboardButton(text="🛒 Driver Market"),
        KeyboardButton(text="🔬 Research"),
    )
    builder.row(
        KeyboardButton(text="💰 Sponsors"),
        KeyboardButton(text="🎁 Daily Reward"),
    )
    return builder.as_markup(resize_keyboard=True)


def team_menu_kb(team_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏎️ Car Stats", callback_data=f"team:car:{team_id}"),
        InlineKeyboardButton(text="👨‍💼 Drivers", callback_data=f"team:drivers:{team_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="👷 Staff", callback_data=f"team:staff:{team_id}"),
        InlineKeyboardButton(text="🏭 Facilities", callback_data=f"team:facilities:{team_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="💰 Budget", callback_data=f"team:budget:{team_id}"),
        InlineKeyboardButton(text="🏅 Achievements", callback_data=f"team:achievements:{team_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⬆️ Upgrade Car", callback_data=f"upgrade:menu:{team_id}"),
    )
    return builder.as_markup()


def upgrade_menu_kb(team_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    stats = [
        ("⚙️ Engine", "engine"),
        ("🌬️ Aerodynamics", "aerodynamics"),
        ("🏗️ Chassis", "chassis"),
        ("🔧 Reliability", "reliability"),
        ("🛞 Tyres", "tyres"),
        ("🔩 Pit Crew", "pit_crew"),
    ]
    for label, stat in stats:
        builder.button(text=label, callback_data=f"upgrade:stat:{team_id}:{stat}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data=f"team:menu:{team_id}"))
    return builder.as_markup()


def strategy_kb(race_id: int, driver_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    strategies = [
        ("1️⃣ 1-Stop", "1stop"), ("2️⃣ 2-Stop", "2stop"), ("3️⃣ 3-Stop", "3stop"),
        ("⚡ Aggressive", "aggressive"), ("⚖️ Balanced", "balanced"), ("🛡️ Conservative", "conservative"),
    ]
    for label, strat in strategies:
        builder.button(text=label, callback_data=f"strategy:set:{race_id}:{driver_id}:{strat}")
    builder.adjust(2)
    return builder.as_markup()


def tyre_selection_kb(race_id: int, driver_id: int, strategy: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    tyres = [("🔴 Soft", "soft"), ("🟡 Medium", "medium"), ("⚪ Hard", "hard")]
    for label, compound in tyres:
        builder.button(
            text=label,
            callback_data=f"tyre:set:{race_id}:{driver_id}:{strategy}:{compound}"
        )
    return builder.as_markup()


def market_kb(page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🆓 Free Agents", callback_data=f"market:free:{page}"),
        InlineKeyboardButton(text="💸 Transfer List", callback_data=f"market:transfers:{page}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔨 Auctions", callback_data=f"market:auctions:{page}"),
        InlineKeyboardButton(text="📤 Sell Driver", callback_data="market:sell"),
    )
    return builder.as_markup()


def league_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Create League", callback_data="league:create"),
        InlineKeyboardButton(text="🔗 Join League", callback_data="league:join"),
    )
    builder.row(
        InlineKeyboardButton(text="🌍 Public Leagues", callback_data="league:public"),
        InlineKeyboardButton(text="ℹ️ My League", callback_data="league:mine"),
    )
    return builder.as_markup()


def sponsors_kb(team_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 My Sponsors", callback_data=f"sponsor:my:{team_id}"),
        InlineKeyboardButton(text="🔍 Find Sponsors", callback_data=f"sponsor:browse:{team_id}:0"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Terminate Contract", callback_data=f"sponsor:terminate_menu:{team_id}"),
    )
    return builder.as_markup()


def sponsor_sign_kb(team_id: int, sponsor_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Sign Contract", callback_data=f"sponsor:sign:{team_id}:{sponsor_id}"),
        InlineKeyboardButton(text="◀️ Back", callback_data=f"sponsor:browse:{team_id}:0"),
    )
    return builder.as_markup()


def sponsor_terminate_kb(team_id: int, sponsor_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚠️ Terminate Early (fee applies)", callback_data=f"sponsor:terminate:{team_id}:{sponsor_id}:early"),
        InlineKeyboardButton(text="❌ Cancel", callback_data=f"sponsor:my:{team_id}"),
    )
    return builder.as_markup()


def research_kb(team_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    trees = [
        ("⚡ Power Unit", "power_unit"),
        ("🌬️ Aerodynamics", "aero"),
        ("⚖️ Weight Reduction", "weight_reduction"),
        ("🔧 Reliability", "reliability"),
        ("🛞 Tyre Tech", "tyres"),
    ]
    for label, tree in trees:
        builder.button(text=label, callback_data=f"research:tree:{team_id}:{tree}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_kb(action: str, confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"✅ Yes, {action}", callback_data=confirm_data),
        InlineKeyboardButton(text="❌ Cancel", callback_data=cancel_data),
    )
    return builder.as_markup()


def pagination_kb(prefix: str, current: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if current > 0:
        builder.button(text="◀️ Prev", callback_data=f"{prefix}:{current - 1}")
    builder.button(text=f"{current + 1}/{total}", callback_data="noop")
    if current < total - 1:
        builder.button(text="Next ▶️", callback_data=f"{prefix}:{current + 1}")
    builder.adjust(3)
    return builder.as_markup()
