"""Настройки seller-бота: приветствие покупателя, кнопка витрины, каналы заявок,
профиль бота в Telegram.

Меню живёт в самом seller-боте: продавец попадает сюда командой /settings или
по диплинку «⚙️ Настройки бота» из хаб-бота (t.me/<bot>?start=settings).

Изоляция по bot_id здесь бесплатна и обязательна одновременно: апдейты
приходят на вебхук конкретного бота, и всё, что читается/меняется, ключуется
на bot_record.id — чужие магазины из этого хендлера не видны в принципе.

Язык. Весь маршрут говорит на языке продавца из /lang hub-бота
(sellers.locale, правило — services/seller_texts.py): владелец у hub-бота и
seller-бота один и тот же человек, второй переключатель ему не нужен.
Проверка владельца возвращает саму строку Seller — из неё и берётся язык,
второго запроса в БД нет. Единственная строка не из словаря — OWNER_ONLY:
чужак, набравший диплинк, получает русский алерт, как и раньше (его язык мы
не знаем, а исторический текст менять незачем).
"""

import html

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.db import get_session
from app.models import Channel, Seller, SellerBot, ShopLogo
from app.services.channels import deactivate_channel_by_id
from app.services.seller_texts import seller_text as _t

router = Router(name="seller_settings")

# Текст кнопки меню бота по умолчанию — одинаков для всех языков (на этом
# пути продаёт продавец, а не платформа); runner читает константу отсюда.
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


async def owner_of(bot_record: SellerBot, tg_user) -> Seller | None:
    """Владелец магазина, если это он нажал/написал; иначе None.

    Диплинк на настройки может набрать кто угодно — меню открывается только
    продавцу, остальные получают обычное приветствие покупателя. Возвращаем
    строку Seller, а не bool: из неё берётся язык экранов."""
    if tg_user is None:
        return None
    async with get_session() as session:
        seller = await session.get(Seller, bot_record.seller_id)
    if seller is None or seller.telegram_id != tg_user.id:
        return None
    return seller


async def is_owner(bot_record: SellerBot, tg_user) -> bool:
    """Совместимость с handlers/seller/start.py (диплинк ?start=settings)."""
    return await owner_of(bot_record, tg_user) is not None


async def _seller_of(bot_record: SellerBot) -> Seller | None:
    """Владелец для языка, когда проверка доступа уже пройдена выше
    (диплинк из start.py, FSM-ответы: чужой в это состояние не попадёт)."""
    async with get_session() as session:
        return await session.get(Seller, bot_record.seller_id)


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


def _channel_id(callback: types.CallbackQuery) -> int | None:
    try:
        return int((callback.data or "").split(":")[-1])
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Меню настроек
# --------------------------------------------------------------------------


def settings_text(bot_record: SellerBot, channels_count: int, seller: Seller | None = None) -> str:
    state_key = "settings.state.on" if bot_record.show_catalog_button else "settings.state.off"
    # текст продавца идёт в сообщение с parse_mode=HTML: один «<» — и меню
    # перестаёт отправляться, а починить его из бота уже нельзя
    btn_text = html.escape(bot_record.catalog_button_text or DEFAULT_BUTTON_TEXT)
    # обрезаем до экранирования: иначе срез может разрубить «&amp;» пополам
    welcome = html.escape(
        (bot_record.welcome_text or _t(seller, "settings.default_welcome"))[:120]
    )
    return _t(
        seller,
        "settings.menu",
        username=bot_record.bot_username,
        welcome=welcome,
        button=btn_text,
        state=_t(seller, state_key),
        channels=channels_count,
    )


def settings_keyboard(
    bot_record: SellerBot, channels_count: int, seller: Seller | None = None
) -> types.InlineKeyboardMarkup:
    short = "settings.state.short_on" if bot_record.show_catalog_button else "settings.state.short_off"
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(seller, "settings.btn.welcome"), callback_data="set:welcome")
    kb.button(
        text=_t(seller, "settings.btn.catalog_toggle", state=_t(seller, short)),
        callback_data="set:btn_toggle",
    )
    kb.button(text=_t(seller, "settings.btn.button_text"), callback_data="set:btn_text")
    kb.button(text=_t(seller, "settings.btn.channels", n=channels_count), callback_data="set:channels")
    kb.button(text=_t(seller, "settings.btn.profile"), callback_data="set:profile")
    kb.button(text=_t(seller, "settings.btn.close"), callback_data="set:close")
    kb.adjust(1)
    return kb.as_markup()


async def show_settings_menu(
    message: types.Message, bot_record: SellerBot, seller: Seller | None = None
) -> None:
    if seller is None:
        seller = await _seller_of(bot_record)
    channels = await _bot_channels(bot_record.id)
    await message.answer(
        settings_text(bot_record, len(channels), seller),
        reply_markup=settings_keyboard(bot_record, len(channels), seller),
    )


async def _edit_menu(
    message: types.Message, bot_record: SellerBot, state: FSMContext, seller: Seller
) -> None:
    await state.clear()
    channels = await _bot_channels(bot_record.id)
    await message.edit_text(
        settings_text(bot_record, len(channels), seller),
        reply_markup=settings_keyboard(bot_record, len(channels), seller),
    )


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, bot_record: SellerBot) -> None:
    seller = await owner_of(bot_record, message.from_user)
    if seller is None:
        await message.answer(OWNER_ONLY)
        return
    await show_settings_menu(message, bot_record, seller)


@router.callback_query(F.data == "set:menu")
async def back_to_menu(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await _edit_menu(callback.message, bot_record, state, seller)


@router.callback_query(F.data == "set:close")
async def close_menu(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
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
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    await state.set_state(SettingsStates.waiting_welcome)
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text=_t(seller, "settings.btn.reset_default"), callback_data="set:welcome_reset")
        kb.button(text=_t(seller, "settings.btn.back"), callback_data="set:menu")
        kb.adjust(1)
        current = html.escape(
            bot_record.welcome_text or _t(seller, "settings.welcome.current_default")
        )
        await callback.message.edit_text(
            _t(seller, "settings.welcome.prompt", current=current),
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data == "set:welcome_reset")
async def reset_welcome(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer(_t(seller, "settings.toast.reset"))
    bot = await _update_bot(bot_record.id, welcome_text=None)
    if callback.message and bot is not None:
        await _edit_menu(callback.message, bot, state, seller)


@router.message(SettingsStates.waiting_welcome, F.text)
async def save_welcome(
    message: types.Message, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await _seller_of(bot_record)
    text = (message.text or "").strip()
    if text.lower() in {"/cancel", "/start"} or not text:
        await message.answer(_t(seller, "settings.no_changes"))
        await show_settings_menu(message, bot_record, seller)
        return
    bot = await _update_bot(bot_record.id, welcome_text=text[:4000])
    await state.clear()
    await message.answer(_t(seller, "settings.welcome.saved"))
    if bot is not None:
        await show_settings_menu(message, bot, seller)


# --------------------------------------------------------------------------
# Кнопка открытия каталога в витрине бота
# --------------------------------------------------------------------------


@router.callback_query(F.data == "set:btn_toggle")
async def toggle_catalog_button(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    bot = await _update_bot(
        bot_record.id, show_catalog_button=not bot_record.show_catalog_button
    )
    await _refresh_menu_button(bot)
    if callback.message and bot is not None:
        await _edit_menu(callback.message, bot, state, seller)


@router.callback_query(F.data == "set:btn_text")
async def ask_button_text(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    await state.set_state(SettingsStates.waiting_button_text)
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text=_t(seller, "settings.btn.reset_default_m"), callback_data="set:btn_text_reset")
        kb.button(text=_t(seller, "settings.btn.back"), callback_data="set:menu")
        kb.adjust(1)
        current = html.escape(bot_record.catalog_button_text or DEFAULT_BUTTON_TEXT)
        await callback.message.edit_text(
            _t(seller, "settings.button.prompt", current=current),
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data == "set:btn_text_reset")
async def reset_button_text(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer(_t(seller, "settings.toast.reset"))
    bot = await _update_bot(bot_record.id, catalog_button_text=None)
    await _refresh_menu_button(bot)
    if callback.message and bot is not None:
        await _edit_menu(callback.message, bot, state, seller)


@router.message(SettingsStates.waiting_button_text, F.text)
async def save_button_text(
    message: types.Message, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await _seller_of(bot_record)
    text = (message.text or "").strip()
    if text.lower() in {"/cancel", "/start"} or not text:
        await message.answer(_t(seller, "settings.no_changes"))
        await show_settings_menu(message, bot_record, seller)
        return
    bot = await _update_bot(bot_record.id, catalog_button_text=text[:64])
    await state.clear()
    await _refresh_menu_button(bot)
    await message.answer(_t(seller, "settings.button.saved"))
    if bot is not None:
        await show_settings_menu(message, bot, seller)


# --------------------------------------------------------------------------
# Каналы приёма заявок (авто-accept + приветствие вступившему)
# --------------------------------------------------------------------------


def channels_text(channels: list[Channel], seller: Seller | None = None) -> str:
    return _t(seller, "settings.channels.list" if channels else "settings.channels.empty")


def channels_keyboard(
    channels: list[Channel], seller: Seller | None = None
) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        icon = "🟢" if ch.auto_accept else "⚪"
        kb.button(text=f"{icon} {ch.title}", callback_data=f"set:ch:{ch.id}")
    kb.button(text=_t(seller, "settings.btn.channel_help"), callback_data="set:ch_help")
    kb.button(text=_t(seller, "settings.btn.back"), callback_data="set:menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "set:channels")
async def show_channels(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    channels = await _bot_channels(bot_record.id)
    if callback.message:
        await callback.message.edit_text(
            channels_text(channels, seller), reply_markup=channels_keyboard(channels, seller)
        )


@router.callback_query(F.data == "set:ch_help")
async def channels_help(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text=_t(seller, "settings.btn.back"), callback_data="set:channels")
        kb.adjust(1)
        await callback.message.edit_text(
            _t(seller, "settings.channels.help", username=bot_record.bot_username),
            reply_markup=kb.as_markup(),
        )


def channel_text(channel: Channel, seller: Seller | None = None) -> str:
    auto = _t(seller, "settings.channel.auto_on" if channel.auto_accept else "settings.channel.auto_off")
    # название канала приходит из Telegram и тоже может содержать «<»
    greeting = html.escape(
        (channel.greeting_text or _t(seller, "settings.channel.default_greeting"))[:200]
    )
    return _t(
        seller,
        "settings.channel.card",
        title=html.escape(channel.title),
        auto=auto,
        greeting=greeting,
    )


async def _own_channel(bot_record: SellerBot, channel_id: int | None) -> Channel | None:
    if channel_id is None:
        return None
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
    if channel is None or channel.bot_id != bot_record.id or not channel.is_active:
        return None
    return channel


def channel_keyboard(channel: Channel, seller: Seller | None = None) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t(seller, "settings.btn.auto_off" if channel.auto_accept else "settings.btn.auto_on"),
        callback_data=f"set:ch_auto:{channel.id}",
    )
    kb.button(text=_t(seller, "settings.btn.channel_greeting"), callback_data=f"set:ch_greet:{channel.id}")
    kb.button(text=_t(seller, "settings.btn.channel_remove"), callback_data=f"set:ch_del:{channel.id}")
    kb.button(text=_t(seller, "settings.btn.back"), callback_data="set:channels")
    kb.adjust(1)
    return kb.as_markup()


async def _render_channel(message: types.Message, channel: Channel, seller: Seller) -> None:
    await message.edit_text(channel_text(channel, seller), reply_markup=channel_keyboard(channel, seller))


@router.callback_query(F.data.startswith("set:ch:"))
async def channel_menu(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    channel = await _own_channel(bot_record, _channel_id(callback))
    if channel is None:
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await _render_channel(callback.message, channel, seller)


@router.callback_query(F.data.startswith("set:ch_auto:"))
async def toggle_auto_accept(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    current = await _own_channel(bot_record, _channel_id(callback))
    if current is None:
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    channel = await _update_channel(bot_record.id, current.id, auto_accept=not current.auto_accept)
    if channel is None:
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    await callback.answer(
        _t(seller, "settings.toast.enabled" if channel.auto_accept else "settings.toast.disabled")
    )
    if callback.message:
        # перерисовываем подменю канала с новым состоянием
        await _render_channel(callback.message, channel, seller)


@router.callback_query(F.data.startswith("set:ch_del:"))
async def confirm_remove_channel(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    channel = await _own_channel(bot_record, _channel_id(callback))
    if channel is None:
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    await callback.answer()
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(text=_t(seller, "settings.btn.yes_remove"), callback_data=f"set:ch_del_yes:{channel.id}")
        kb.button(text=_t(seller, "settings.btn.cancel"), callback_data=f"set:ch:{channel.id}")
        kb.adjust(1)
        await callback.message.edit_text(
            _t(seller, "settings.channel.remove_confirm", title=html.escape(channel.title)),
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("set:ch_del_yes:"))
async def do_remove_channel(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    channel_id = _channel_id(callback)
    if channel_id is None or not await deactivate_channel_by_id(bot_record.id, channel_id):
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    await callback.answer(_t(seller, "settings.toast.channel_removed"))
    if callback.message:
        channels = await _bot_channels(bot_record.id)
        await callback.message.edit_text(
            channels_text(channels, seller), reply_markup=channels_keyboard(channels, seller)
        )


@router.callback_query(F.data.startswith("set:ch_greet:"))
async def ask_greeting(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    channel = await _own_channel(bot_record, _channel_id(callback))
    if channel is None:
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    await callback.answer()
    await state.set_state(SettingsStates.waiting_greeting)
    await state.update_data(channel_id=channel.id)
    if callback.message:
        kb = InlineKeyboardBuilder()
        kb.button(
            text=_t(seller, "settings.btn.reset_default"),
            callback_data=f"set:ch_greet_reset:{channel.id}",
        )
        kb.button(text=_t(seller, "settings.btn.back"), callback_data=f"set:ch:{channel.id}")
        kb.adjust(1)
        current = html.escape(
            channel.greeting_text or _t(seller, "settings.channel.default_greeting")
        )
        await callback.message.edit_text(
            _t(seller, "settings.greeting.prompt", current=current),
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("set:ch_greet_reset:"))
async def reset_greeting(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    channel_id = _channel_id(callback)
    if channel_id is None:
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    channel = await _update_channel(bot_record.id, channel_id, greeting_text=None)
    if channel is None:
        await callback.answer(_t(seller, "settings.alert.channel_not_found"), show_alert=True)
        return
    await callback.answer(_t(seller, "settings.toast.reset"))
    await state.clear()
    if callback.message:
        # возврат к подменю канала со свежими данными
        await _render_channel(callback.message, channel, seller)


@router.message(SettingsStates.waiting_greeting, F.text)
async def save_greeting(
    message: types.Message, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await _seller_of(bot_record)
    data = await state.get_data()
    channel_id = data.get("channel_id")
    text = (message.text or "").strip()

    if text.lower() in {"/cancel", "/start"}:
        await message.answer(_t(seller, "settings.no_changes"))
        await show_settings_menu(message, bot_record, seller)
        return

    if text.lower() == "/reset":
        channel = await _update_channel(bot_record.id, channel_id, greeting_text=None)
    else:
        channel = await _update_channel(bot_record.id, channel_id, greeting_text=text[:2000])

    await state.clear()
    if channel is None:
        await message.answer(_t(seller, "settings.channel.gone"))
        await show_settings_menu(message, bot_record, seller)
        return
    await message.answer(_t(seller, "settings.greeting.saved"))
    await show_channels_message(message, bot_record, seller)


async def show_channels_message(
    message: types.Message, bot_record: SellerBot, seller: Seller | None = None
) -> None:
    """Список каналов новым сообщением (для сохранения после ввода текста)."""
    if seller is None:
        seller = await _seller_of(bot_record)
    channels = await _bot_channels(bot_record.id)
    await message.answer(
        channels_text(channels, seller), reply_markup=channels_keyboard(channels, seller)
    )


# --------------------------------------------------------------------------
# Профиль бота в Telegram: имя и аватар из кабинета (services/bot_profile.py).
# Здесь их не редактируют — только смотрят и досылают в Telegram: для
# магазинов, подключённых до синхронизации, и после неудачной попытки.
# --------------------------------------------------------------------------


async def _fresh_bot(bot_id: int) -> tuple[SellerBot | None, bytes | None]:
    """Актуальная строка бота и байты лого: bot_record из middleware мог быть
    прочитан до правок в кабинете, а лого нужно самому сервису."""
    async with get_session() as session:
        bot = await session.get(SellerBot, bot_id)
        logo = (
            await session.execute(select(ShopLogo.data).where(ShopLogo.bot_id == bot_id))
        ).scalar_one_or_none()
    return bot, logo


def profile_text(bot_record: SellerBot, has_logo: bool, seller: Seller) -> str:
    default = bot_record.default_bot_name
    return _t(
        seller,
        "settings.profile",
        name=html.escape(bot_record.shop_name or bot_record.default_bot_name or f"@{bot_record.bot_username}"),
        default=html.escape(default) if default else _t(seller, "settings.profile.unknown"),
        logo=_t(seller, "settings.profile.logo_yes" if has_logo else "settings.profile.logo_no"),
    )


def profile_keyboard(seller: Seller) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(seller, "settings.btn.profile_sync"), callback_data="set:profile_sync")
    kb.button(text=_t(seller, "settings.btn.back"), callback_data="set:menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "set:profile")
async def show_profile(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    await callback.answer()
    await state.clear()
    bot, logo = await _fresh_bot(bot_record.id)
    if callback.message and bot is not None:
        await callback.message.edit_text(
            profile_text(bot, logo is not None, seller), reply_markup=profile_keyboard(seller)
        )


def _sync_summary(seller: Seller, results: dict) -> str:
    """Один тост из двух исходов (имя, аватар)."""
    statuses = {key: r.status for key, r in results.items()}
    done = [key for key, st in statuses.items() if st == "ok"]
    limited = next((r for r in results.values() if r.status == "rate_limited"), None)
    if limited is not None:
        return _t(seller, "settings.profile.sync_rate_limited", seconds=limited.retry_after or 60)
    if any(st == "failed" for st in statuses.values()):
        return _t(seller, "settings.profile.sync_failed")
    if not done:
        return _t(seller, "settings.profile.sync_skipped")
    if len(done) == len(results):
        return _t(seller, "settings.profile.sync_ok")
    details = ", ".join(_t(seller, f"settings.profile.part.{key}") for key in done)
    return _t(seller, "settings.profile.sync_partial", details=details)


@router.callback_query(F.data == "set:profile_sync")
async def sync_profile(
    callback: types.CallbackQuery, state: FSMContext, bot_record: SellerBot
) -> None:
    seller = await owner_of(bot_record, callback.from_user)
    if seller is None:
        await callback.answer(OWNER_ONLY, show_alert=True)
        return
    from app.services.bot_profile import sync_bot_profile

    bot, logo = await _fresh_bot(bot_record.id)
    if bot is None:
        await callback.answer(_t(seller, "alert.bot_not_found"), show_alert=True)
        return
    results = await sync_bot_profile(bot, logo)
    # без аватара нечего досылать — но «пропущено» из-за отсутствия лого не
    # должно портить итог, если имя ушло
    if logo is None:
        results.pop("photo", None)
    await callback.answer(_sync_summary(seller, results), show_alert=True)
    if callback.message:
        try:
            await callback.message.edit_text(
                profile_text(bot, logo is not None, seller), reply_markup=profile_keyboard(seller)
            )
        except Exception:
            pass  # текст не изменился — Telegram отвечает «message is not modified»
