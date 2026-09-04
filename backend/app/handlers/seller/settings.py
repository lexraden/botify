"""Настройки seller-бота: приветствие покупателя, кнопка витрины, каналы заявок.

Меню живёт в самом seller-боте: продавец попадает сюда командой /settings или
по диплинку «⚙️ Настройки бота» из хаб-бота (t.me/<bot>?start=settings).

Изоляция по bot_id здесь бесплатна и обязательна одновременно: апдейты
приходят на вебхук конкретного бота, и всё, что читается/меняется, ключуется
на bot_record.id — чужие магазины из этого хендлера не видны в принципе.
"""

import html

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.db import get_session
from app.models import Channel, Seller, SellerBot
from app.services.channels import deactivate_channel_by_id

router = Router(name="seller_settings")

DEFAULT_BUTTON_TEXT = "Open"
OWNER_ONLY = "Настройки доступны только владельцу магазина."


class SettingsStates(StatesGroup):
    waiting_welcome = State()
    waiting_button_text = State()
    waiting_greeting = State()


async def _refresh_menu_button(bot: SellerBot | None) -> None:
    """Кнопка меню бота берёт текст из catalog_button_text — после его смены
    (или смены настроек кнопки) переустанавливаем её. Ленивый импорт: runner
    импортирует хендлеры, обратный импорт на уровне модуля дал бы цикл."""
    if bot is None:
        return
    from app.bots.runner import apply_seller_menu_button

    await apply_seller_menu_button(bot)


# --------------------------------------------------------------------------
# Доступ и данные: всё строго в контексте одного бота
# --------------------------------------------------------------------------


async def is_owner(bot_record: SellerBot, tg_user) -> bool:
    """Диплинк на настройки может набрать кто угодно — меню открывается
    только продавцу, остальные получают обычное приветствие покупателя."""
    if tg_user is None:
        return False
    async with get_session() as session:
        seller = await session.get(Seller, bot_record.seller_id)
    return seller is not None and seller.telegram_id == tg_user.id


async def _bot_channels(bot_id: int) -> list[Channel]:
    async with get_session() as session:
        result = await session.execute(
            select(Channel)
            .where(Channel.bot_id == bot_id, Channel.is_active.is_(True))
            .order_by(Channel.id)
        )
        return list(result.scalars().all())


async def _update_bot(bot_id: int, **fields) -> SellerBot | None:
    async with get_session() as session:
        bot = await session.get(SellerBot, bot_id)
        if bot is None:
            return None
        for key, value in fields.items():
            setattr(bot, key, value)
        await session.commit()
        return bot


async def _update_channel(bot_id: int, channel_id: int, **fields) -> Channel | None:
    """Канал достаётся только по паре (bot_id, channel_id) — чужой не тронем."""
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel is None or channel.bot_id != bot_id:
            return None
        for key, value in fields.items():
            setattr(channel, key, value)
        await session.commit()
        return channel


# --------------------------------------------------------------------------
# Меню настроек
# --------------------------------------------------------------------------


def settings_text(bot_record: SellerBot, channels_count: int) -> str:
    button = "включена" if bot_record.show_catalog_button else "выключена"
    # текст продавца идёт в сообщение с parse_mode=HTML: один «<» — и меню
    # перестаёт отправляться, а починить его из бота уже нельзя
    btn_text = html.escape(bot_record.catalog_button_text or DEFAULT_BUTTON_TEXT)
    # обрезаем до экранирования: иначе срез может разрубить «&amp;» пополам
    welcome = html.escape((bot_record.welcome_text or "стандартное приветствие")[:120])
    return (
        f"⚙️ <b>Настройки бота @{bot_record.bot_username}</b>\n\n"
        f"👋 Приветствие на /start:\n<i>{welcome}</i>\n\n"
        f"🔘 Кнопка «{btn_text}»: {button}\n"
        f"📢 Каналы для приёма заявок: {channels_count}"
    )


def settings_keyboard(bot_record: SellerBot, channels_count: int) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✍️ Приветствие", callback_data="set:welcome")
    kb.button(
        text=f"🔘 Кнопка каталога: {'вкл' if bot_record.show_catalog_button else 'выкл'}",
        callback_data="set:btn_toggle",
    )
    kb.button(text="✏️ Текст кнопки", callback_data="set:btn_text")
    kb.button(text=f"📢 Каналы ({channels_count})", callback_data="set:channels")
    kb.button(text="✖️ Закрыть", callback_data="set:close")
    kb.adjust(1)
    return kb.as_markup()


async def show_settings_menu(message: types.Message, bot_record: SellerBot) -> None:
    channels = await _bot_channels(bot_record.id)
    await message.answer(
        settings_text(bot_record, len(channels)),
        reply_markup=settings_keyboard(bot_record, len(channels)),
    )


async def _edit_menu(
    message: types.Message, bot_record: SellerBot, state: FSMContext
) -> None:
    await state.clear()
    channels = await _bot_channels(bot_record.id)
    await message.edit_text(
        settings_text(bot_record, len(channels)),
        reply_markup=settings_keyboard(bot_record, len(channels)),
    )


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, bot_record: SellerBot) -> None:
    if not await is_owner(bot_record, message.from_user):
        await message.answer(OWNER_ONLY)
        return
    await show_settings_menu(message, bot_record)


@router.callback_query(F.data == "set:menu")
async def back_to_menu(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await _edit_menu(callback.message, bot_record, state)


@router.callback_query(F.data == "set:close")
async def close_menu(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await state.clear()
    await callback.answer()
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass  # сообщение старше 48 часов — просто оставляем его


# --------------------------------------------------------------------------
# Приветствие покупателю
# --------------------------------------------------------------------------


@router.callback_query(F.data == "set:welcome")
async def ask_welcome(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    await state.set_state(SettingsStates.waiting_welcome)
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text="Сбросить на стандартное", callback_data="set:welcome_reset")
        kb.button(text="⬅️ Назад", callback_data="set:menu")
        kb.adjust(1)
        current = html.escape(bot_record.welcome_text or "— стандартное приветствие —")
        await callback.message.edit_text(
            "Пришли новый текст приветствия — его увидит покупатель на /start.\n"
            'Можно использовать HTML: <b>&lt;b&gt;</b>, <b>&lt;i&gt;</b>, <b>&lt;a href="…"&gt;</b>\n\n'
            f"Сейчас:\n{current}",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data == "set:welcome_reset")
async def reset_welcome(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer("Сброшено")
    bot = await _update_bot(bot_record.id, welcome_text=None)
    if callback.message and bot is not None:
        await _edit_menu(callback.message, bot, state)


@router.message(SettingsStates.waiting_welcome, F.text)
async def save_welcome(
    message: types.Message, state: FSMContext, bot_record: SellerBot
) -> None:
    text = (message.text or "").strip()
    if text.lower() in {"/cancel", "/start"} or not text:
        await message.answer("Хорошо, без изменений.")
        await show_settings_menu(message, bot_record)
        return
    bot = await _update_bot(bot_record.id, welcome_text=text[:4000])
    await state.clear()
    await message.answer("✅ Приветствие сохранено")
    if bot is not None:
        await show_settings_menu(message, bot)


# --------------------------------------------------------------------------
# Кнопка открытия каталога в витрине бота
# --------------------------------------------------------------------------


@router.callback_query(F.data == "set:btn_toggle")
async def toggle_catalog_button(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    bot = await _update_bot(
        bot_record.id, show_catalog_button=not bot_record.show_catalog_button
    )
    await _refresh_menu_button(bot)
    if callback.message and bot is not None:
        await _edit_menu(callback.message, bot, state)


@router.callback_query(F.data == "set:btn_text")
async def ask_button_text(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    await state.set_state(SettingsStates.waiting_button_text)
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text="Сбросить на стандартный", callback_data="set:btn_text_reset")
        kb.button(text="⬅️ Назад", callback_data="set:menu")
        kb.adjust(1)
        current = html.escape(bot_record.catalog_button_text or DEFAULT_BUTTON_TEXT)
        await callback.message.edit_text(
            "Пришли новый текст кнопки открытия магазина (до 64 символов).\n\n"
            f"Сейчас: {current}",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data == "set:btn_text_reset")
async def reset_button_text(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer("Сброшено")
    bot = await _update_bot(bot_record.id, catalog_button_text=None)
    await _refresh_menu_button(bot)
    if callback.message and bot is not None:
        await _edit_menu(callback.message, bot, state)


@router.message(SettingsStates.waiting_button_text, F.text)
async def save_button_text(
    message: types.Message, state: FSMContext, bot_record: SellerBot
) -> None:
    text = (message.text or "").strip()
    if text.lower() in {"/cancel", "/start"} or not text:
        await message.answer("Хорошо, без изменений.")
        await show_settings_menu(message, bot_record)
        return
    bot = await _update_bot(bot_record.id, catalog_button_text=text[:64])
    await state.clear()
    await _refresh_menu_button(bot)
    await message.answer("✅ Текст кнопки сохранён")
    if bot is not None:
        await show_settings_menu(message, bot)


# --------------------------------------------------------------------------
# Каналы приёма заявок (авто-accept + приветствие вступившему)
# --------------------------------------------------------------------------


def channels_text(channels: list[Channel]) -> str:
    if not channels:
        return (
            "📢 <b>Каналы</b>\n\nКаналов пока нет. Добавь бота администратором "
            "в канал — он появится здесь автоматически."
        )
    return (
        "📢 <b>Каналы</b>\n\nЗелёный — заявки принимаются автоматически. "
        "Нажми на канал, чтобы поменять настройки и приветствие вступившим."
    )


def channels_keyboard(channels: list[Channel]) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        icon = "🟢" if ch.auto_accept else "⚪"
        kb.button(text=f"{icon} {ch.title}", callback_data=f"set:ch:{ch.id}")
    kb.button(text="➕ Как подключить канал", callback_data="set:ch_help")
    kb.button(text="⬅️ Назад", callback_data="set:menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "set:channels")
async def show_channels(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    channels = await _bot_channels(bot_record.id)
    if callback.message:
        await callback.message.edit_text(
            channels_text(channels), reply_markup=channels_keyboard(channels)
        )


@router.callback_query(F.data == "set:ch_help")
async def channels_help(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Назад", callback_data="set:channels")
        kb.adjust(1)
        await callback.message.edit_text(
            "➕ <b>Как подключить канал</b>\n\n"
            f"1. Добавь бота @{bot_record.bot_username} администратором в свой канал.\n"
            "2. Отметь право «Приглашать пользователей» — без него бот не видит заявки.\n"
            "3. Канал появится в списке автоматически.\n\n"
            "Каждый, кто нажмёт «Подать заявку» в приватном канале, будет "
            "автоматически принят и попадёт в твою базу покупателей.",
            reply_markup=kb.as_markup(),
        )


def channel_text(channel: Channel) -> str:
    auto = "включён 🟢" if channel.auto_accept else "выключен ⚪"
    # название канала приходит из Telegram и тоже может содержать «<»
    greeting = html.escape((channel.greeting_text or "— стандартное приветствие канала —")[:200])
    return (
        f"📢 <b>{html.escape(channel.title)}</b>\n\n"
        f"Авто-приём заявок: {auto}\n"
        f"Приветствие вступившим:\n<i>{greeting}</i>"
    )


async def _own_channel(bot_record: SellerBot, channel_id: int) -> Channel | None:
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
    if channel is None or channel.bot_id != bot_record.id or not channel.is_active:
        return None
    return channel


@router.callback_query(F.data.startswith("set:ch:"))
async def channel_menu(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    try:
        channel_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Канал не найден", show_alert=True)
        return
    channel = await _own_channel(bot_record, channel_id)
    if channel is None:
        await callback.answer("Канал не найден", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            channel_text(channel), reply_markup=channel_keyboard(channel)
        )


def channel_keyboard(channel: Channel) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="Выключить авто-приём" if channel.auto_accept else "Включить авто-приём",
        callback_data=f"set:ch_auto:{channel.id}",
    )
    kb.button(text="✍️ Приветствие вступившим", callback_data=f"set:ch_greet:{channel.id}")
    kb.button(text="🗑 Отключить канал", callback_data=f"set:ch_del:{channel.id}")
    kb.button(text="⬅️ Назад", callback_data="set:channels")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data.startswith("set:ch_auto:"))
async def toggle_auto_accept(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    try:
        channel_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Канал не найден", show_alert=True)
        return
    current = await _own_channel(bot_record, channel_id)
    if current is None:
        await callback.answer("Канал не найден", show_alert=True)
        return
    channel = await _update_channel(
        bot_record.id, channel_id, auto_accept=not current.auto_accept
    )
    if channel is None:
        await callback.answer("Канал не найден", show_alert=True)
        return
    await callback.answer("Выключено" if not channel.auto_accept else "Включено")
    if callback.message and channel is not None:
        # перерисовываем подменю канала с новым состоянием
        await callback.message.edit_text(
            channel_text(channel), reply_markup=channel_keyboard(channel)
        )


@router.callback_query(F.data.startswith("set:ch_del:"))
async def confirm_remove_channel(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    try:
        channel_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Канал не найден", show_alert=True)
        return
    channel = await _own_channel(bot_record, channel_id)
    if channel is None:
        await callback.answer("Канал не найден", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text="Да, отключить", callback_data=f"set:ch_del_yes:{channel.id}")
        kb.button(text="Отмена", callback_data=f"set:ch:{channel.id}")
        kb.adjust(1)
        await callback.message.edit_text(
            f"Отключить канал «{html.escape(channel.title)}»?\n\n"
            "Бот перестанет принимать заявки из него и приветствовать вступивших. "
            "Канал вернётся в список, только если заново добавить бота в канал.",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("set:ch_del_yes:"))
async def do_remove_channel(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    try:
        channel_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Канал не найден", show_alert=True)
        return
    if not await deactivate_channel_by_id(bot_record.id, channel_id):
        await callback.answer("Канал не найден", show_alert=True)
        return
    await callback.answer("Канал отключён")
    if callback.message:
        channels = await _bot_channels(bot_record.id)
        await callback.message.edit_text(
            channels_text(channels), reply_markup=channels_keyboard(channels)
        )


@router.callback_query(F.data.startswith("set:ch_greet:"))
async def ask_greeting(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    try:
        channel_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Канал не найден", show_alert=True)
        return
    channel = await _own_channel(bot_record, channel_id)
    if channel is None:
        await callback.answer("Канал не найден", show_alert=True)
        return
    await callback.answer()
    await state.set_state(SettingsStates.waiting_greeting)
    await state.update_data(channel_id=channel.id)
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text="Сбросить на стандартное", callback_data=f"set:ch_greet_reset:{channel.id}")
        kb.button(text="⬅️ Назад", callback_data=f"set:ch:{channel.id}")
        kb.adjust(1)
        current = html.escape(channel.greeting_text or "— стандартное приветствие канала —")
        await callback.message.edit_text(
            "Пришли приветствие, которое бот отправит вступившему в ЛС.\n"
            "/reset — вернуть стандартное.\n\n"
            f"Сейчас:\n{current}",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("set:ch_greet_reset:"))
async def reset_greeting(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    if not await is_owner(bot_record, callback.from_user):
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    try:
        channel_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("Канал не найден", show_alert=True)
        return
    channel = await _update_channel(bot_record.id, channel_id, greeting_text=None)
    if channel is None:
        await callback.answer("Канал не найден", show_alert=True)
        return
    await callback.answer("Сброшено")
    await state.clear()
    if callback.message:
        # возврат к подменю канала со свежими данными
        callback.data = f"set:ch:{channel.id}"
        await channel_menu(callback, state, bot_record)


@router.message(SettingsStates.waiting_greeting, F.text)
async def save_greeting(
    message: types.Message, state: FSMContext, bot_record: SellerBot
) -> None:
    data = await state.get_data()
    channel_id = data.get("channel_id")
    text = (message.text or "").strip()

    if text.lower() in {"/cancel", "/start"}:
        await message.answer("Хорошо, без изменений.")
        await show_settings_menu(message, bot_record)
        return

    if text.lower() == "/reset":
        channel = await _update_channel(bot_record.id, channel_id, greeting_text=None)
    else:
        channel = await _update_channel(bot_record.id, channel_id, greeting_text=text[:2000])

    await state.clear()
    if channel is None:
        await message.answer("Канал не найден — возможно, он уже отключён.")
        await show_settings_menu(message, bot_record)
        return
    await message.answer("✅ Приветствие сохранено")
    await show_channels_message(message, bot_record)


async def show_channels_message(message: types.Message, bot_record: SellerBot) -> None:
    """Список каналов новым сообщением (для сохранения после ввода текста)."""
    channels = await _bot_channels(bot_record.id)
    await message.answer(channels_text(channels), reply_markup=channels_keyboard(channels))
