"""Управление магазинами: меню «Мои магазины», карточки, включение/удаление.

Все тексты — на языке продавца (services/seller_texts.py); у билдеров текстов
локаль — последний параметр со значением «ru», чтобы прямые вызовы из тестов
и старые места не таили в себе смену языка.
"""

import html

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.models import Seller, SellerBot
from app.services.bot_connect import delete_bot, disconnect_bot, enable_bot, get_own_bot
from app.services.bot_recovery import (
    ALREADY_OK,
    NOT_MANAGED,
    RESTORED,
    WEBHOOK_PENDING,
    restore_managed_token,
)
from app.services.seller_texts import seller_locale, text

router = Router()

STATUS_ICONS = {"active": "🟢", "pending": "🟡", "failed": "🔴", "revoked": "🔴"}


def restore_keyboard(bot_id: int, locale: str = "ru") -> types.InlineKeyboardMarkup:
    """Кнопка «выпустить новый токен» — для бота, созданного нашей кнопкой.

    Уезжает в пуш от `bot_health`, поэтому живёт здесь, рядом с хендлером,
    который её ловит.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text=text(locale, "btn.restore"), callback_data=f"mybots:fix:{bot_id}")
    return kb.as_markup()


def bot_status_line(bot: SellerBot, locale: str = "ru") -> str:
    """Строка одного магазина в общем списке."""
    if bot.is_draft:
        # магазин заведён, бот ещё не создан — зовём закончить, а не пугаем
        return text(locale, "status.draft", name=html.escape(bot.display_name))
    if not bot.is_active:
        return text(locale, "status.disabled", username=bot.bot_username)
    icon = STATUS_ICONS.get(bot.webhook_status, "⚪")
    if bot.webhook_status == "revoked":
        # отозванный токен чинится только переподключением, поэтому пишем
        # прямо здесь, а не прячем за цветом кружка
        fix = (
            text(locale, "status.fix.managed")
            if bot.is_managed
            else text(locale, "status.fix.unmanaged")
        )
        return text(locale, "status.revoked", icon=icon, username=bot.bot_username, fix=fix)
    return text(locale, "status.active", icon=icon, username=bot.bot_username)


def shops_menu_text(bots: list[SellerBot], locale: str = "ru") -> str:
    lines = "\n".join(bot_status_line(bot, locale) for bot in bots)
    return f"{text(locale, 'shops.header')}\n\n{lines}\n\n{text(locale, 'shops.pitch')}"


def add_shop_button(kb: InlineKeyboardBuilder, locale: str = "ru") -> None:
    """Кнопка «подключить ещё магазин» — диплинк сразу на шаг подключения.

    Гард входа в вебаппе перехватывает только «/», поэтому прямой URL
    /onboarding/bot открывается без редиректа на другие экраны.
    Без настроенного адреса кнопка просто не добавляется.
    """
    webapp_url = get_settings().effective_webapp_url
    if webapp_url:
        kb.button(
            text=text(locale, "btn.add_shop"),
            web_app=types.WebAppInfo(url=f"{webapp_url.rstrip('/')}/onboarding/bot"),
        )


def shop_label(bot: SellerBot) -> str:
    """Как назвать магазин в кнопке или карточке.

    У черновика (магазин заведён через /newshop до создания бота) юзернейма
    нет, и подстановка через f-строку давала кнопку с подписью «@None».
    """
    return f"@{bot.bot_username}" if bot.bot_username else bot.display_name


def shops_menu_keyboard(bots: list[SellerBot], locale: str = "ru") -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for bot in bots:
        kb.button(text=shop_label(bot), callback_data=f"mybots:card:{bot.id}")
    add_shop_button(kb, locale)
    kb.adjust(1)
    return kb.as_markup()


def bot_card_text(bot: SellerBot, locale: str = "ru") -> str:
    if bot.is_draft:
        return text(
            locale, "card.draft", name=html.escape(bot.display_name)
        )
    if bot.webhook_status == "revoked":
        # «работает» здесь было бы враньём: покупатели до магазина не доходят
        return text(locale, "card.revoked", username=bot.bot_username)
    if bot.is_active:
        icon = STATUS_ICONS.get(bot.webhook_status, "⚪")
        return text(locale, "card.active", icon=icon, label=shop_label(bot))
    return text(locale, "card.disabled", label=shop_label(bot))


def bot_card_keyboard(bot: SellerBot, locale: str = "ru") -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if bot.is_draft:
        # включать нечего, а «Настройки бота» вели бы на t.me/None
        kb.button(text=text(locale, "btn.delete"), callback_data=f"mybots:del:{bot.id}")
        kb.button(text=text(locale, "btn.back_all"), callback_data="mybots:menu")
        kb.adjust(1)
        return kb.as_markup()
    if bot.webhook_status == "revoked" and bot.is_managed:
        # починка в одно нажатие — до всех остальных кнопок
        kb.button(text=text(locale, "btn.restore"), callback_data=f"mybots:fix:{bot.id}")
    if bot.is_active:
        kb.button(text=text(locale, "btn.off"), callback_data=f"mybots:off:{bot.id}")
    else:
        kb.button(text=text(locale, "btn.on"), callback_data=f"mybots:on:{bot.id}")
        kb.button(text=text(locale, "btn.delete"), callback_data=f"mybots:del:{bot.id}")
    # админы раздаются здесь же, в хабе: список, приглашение по @username/ID
    kb.button(text=text(locale, "btn.admins"), callback_data=f"mybots:admins:{bot.id}")
    # настройки живут в самом seller-боте: диплинк открывает там /settings
    kb.button(
        text=text(locale, "btn.settings"),
        url=f"https://t.me/{bot.bot_username}?start=settings",
    )
    kb.button(text=text(locale, "btn.back_all"), callback_data="mybots:menu")
    kb.adjust(2)
    return kb.as_markup()


async def _seller_for(telegram_id: int) -> Seller | None:
    async with get_session() as session:
        result = await session.execute(select(Seller).where(Seller.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def owned_bot_from_callback(callback: types.CallbackQuery) -> tuple[Seller, int] | None:
    """Гард callback-ов карточки магазина: callback.data вида «…:{bot_id}».

    Возвращает продавца и id магазина или None с алертом, если человек не
    зарегистрирован или магазин не его. Публичный: используется и хендлерами
    администраторов (app/handlers/hub/shop_admins.py).
    """
    if callback.from_user is None or callback.data is None:
        return None
    seller = await _seller_for(callback.from_user.id)
    if seller is None:
        await callback.answer(text("ru", "alert.start_first"), show_alert=True)
        return None
    bot_id = int(callback.data.split(":")[-1])
    if await get_own_bot(bot_id, seller.id) is None:
        await callback.answer(text(seller_locale(seller), "alert.bot_not_found"), show_alert=True)
        return None
    return seller, bot_id


async def _seller_bots(seller_id: int) -> list[SellerBot]:
    async with get_session() as session:
        bots = (
            (await session.execute(select(SellerBot).where(SellerBot.seller_id == seller_id)))
            .scalars()
            .all()
        )
    return list(bots)


async def send_shops_menu(message: types.Message, seller: Seller) -> None:
    """Меню «Мои магазины» одним сообщением: список со статусами, кнопки
    по каждому магазину и подключение следующего — вместо прежних
    N+1 отдельных сообщений."""
    bots = await _seller_bots(seller.id)
    locale = seller_locale(seller)
    if not bots:
        await message.answer(text(locale, "shops.none"))
        return
    await message.answer(
        shops_menu_text(bots, locale), reply_markup=shops_menu_keyboard(bots, locale)
    )


@router.message(Command("mybots"))
async def my_bots(message: types.Message) -> None:
    if message.from_user is None:
        return
    seller = await _seller_for(message.from_user.id)
    if seller is None:
        await message.answer(text("ru", "msg.register"))
        return
    await send_shops_menu(message, seller)


@router.callback_query(F.data == "mybots:list")
async def my_bots_button(callback: types.CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or callback.message is None:
        return
    seller = await _seller_for(callback.from_user.id)
    if seller is None:
        await callback.message.answer(text("ru", "msg.register"))
        return
    # новым сообщением, а не правкой: под ней стартовый экран
    # с кнопкой «Открыть приложение», его трогать нельзя
    await send_shops_menu(callback.message, seller)


@router.callback_query(F.data == "mybots:menu")
async def back_to_shops_menu(callback: types.CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or callback.message is None:
        return
    seller = await _seller_for(callback.from_user.id)
    if seller is None:
        await callback.message.answer(text("ru", "msg.register"))
        return
    bots = await _seller_bots(seller.id)
    if not bots:
        await callback.message.edit_text(text(seller_locale(seller), "shops.none"))
        return
    await callback.message.edit_text(
        shops_menu_text(bots, seller_locale(seller)),
        reply_markup=shops_menu_keyboard(bots, seller_locale(seller)),
    )


@router.callback_query(F.data.startswith("mybots:card:"))
async def open_bot_card(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    await callback.answer()
    bot = await get_own_bot(bot_id, seller.id)
    if callback.message and bot is not None:
        await callback.message.edit_text(
            bot_card_text(bot, seller_locale(seller)),
            reply_markup=bot_card_keyboard(bot, seller_locale(seller)),
        )


@router.callback_query(F.data.startswith("mybots:off:"))
async def confirm_disconnect(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    locale = seller_locale(seller)
    await callback.answer()
    bot = await get_own_bot(bot_id, seller.id)
    kb = InlineKeyboardBuilder()
    kb.button(text=text(locale, "btn.yes_off"), callback_data=f"mybots:off_yes:{bot_id}")
    kb.button(text=text(locale, "btn.cancel"), callback_data=f"mybots:back:{bot_id}")
    kb.adjust(2)
    # бот мог исчезнуть между списком и нажатием (удалён из другой вкладки) —
    # без гарда подтверждение падало бы на bot_username
    if callback.message and bot is not None:
        await callback.message.edit_text(
            text(locale, "off.confirm", username=bot.bot_username),
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("mybots:off_yes:"))
async def do_disconnect(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    bot = await disconnect_bot(bot_id, seller.id)
    await callback.answer(text(seller_locale(seller), "toast.off"))
    if callback.message and bot is not None:
        await callback.message.edit_text(
            bot_card_text(bot, seller_locale(seller)),
            reply_markup=bot_card_keyboard(bot, seller_locale(seller)),
        )


@router.callback_query(F.data.startswith("mybots:on:"))
async def do_enable(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    locale = seller_locale(seller)
    bot = await enable_bot(bot_id, seller.id)
    if bot is None:
        # черновик: бота нет, включать нечего — раньше тост всё равно
        # рапортовал «Включён», хотя не произошло ничего
        await callback.answer(text(locale, "alert.draft_no_bot"), show_alert=True)
        return
    await callback.answer(text(locale, "toast.on"))
    if callback.message:
        await callback.message.edit_text(
            bot_card_text(bot, locale), reply_markup=bot_card_keyboard(bot, locale)
        )


@router.callback_query(F.data.startswith("mybots:del:"))
async def confirm_delete(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    locale = seller_locale(seller)
    await callback.answer()
    bot = await get_own_bot(bot_id, seller.id)
    kb = InlineKeyboardBuilder()
    kb.button(text=text(locale, "btn.yes_delete"), callback_data=f"mybots:del_yes:{bot_id}")
    kb.button(text=text(locale, "btn.cancel"), callback_data=f"mybots:back:{bot_id}")
    kb.adjust(1)
    # тот же гард, что и в confirm_disconnect: бота могли уже удалить
    if callback.message and bot is not None:
        await callback.message.edit_text(
            text(locale, "del.confirm", label=shop_label(bot)),
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("mybots:del_yes:"))
async def do_delete(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    locale = seller_locale(seller)
    bot = await get_own_bot(bot_id, seller.id)
    result = await delete_bot(bot_id, seller.id)
    if callback.message is None:
        return
    if result == "deleted":
        await callback.answer(text(locale, "toast.deleted"))
        # сразу назад к списку: видно, что магазин исчез, и можно
        # тут же подключить следующий
        bots = await _seller_bots(seller.id)
        if bots:
            await callback.message.edit_text(
                shops_menu_text(bots, locale),
                reply_markup=shops_menu_keyboard(bots, locale),
            )
        else:
            await callback.message.edit_text(text(locale, "shops.none"))
    elif result == "has_orders":
        await callback.answer()
        kb = InlineKeyboardBuilder()
        kb.button(text=text(locale, "btn.back_all"), callback_data="mybots:menu")
        kb.adjust(1)
        await callback.message.edit_text(
            text(locale, "del.has_orders", username=bot.bot_username),
            reply_markup=kb.as_markup(),
        )
    else:
        await callback.answer(text(locale, "alert.bot_not_found"), show_alert=True)


@router.callback_query(F.data.startswith("mybots:fix:"))
async def restore_shop(callback: types.CallbackQuery) -> None:
    """Перевыпуск токена бота, созданного нашей кнопкой.

    Кнопка приходит двумя путями: в пуше от `bot_health` и в карточке
    магазина, — поэтому правим не сообщение целиком, а отвечаем текстом:
    под кнопкой может быть и то и другое.
    """
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    locale = seller_locale(seller)
    if callback.message is None:
        return

    await callback.answer(text(locale, "restore.doing"))
    result = await restore_managed_token(bot_id, seller.id)
    bot = await get_own_bot(bot_id, seller.id)
    username = bot.bot_username if bot else ""

    if result == RESTORED:
        text_out = text(locale, "restore.restored", username=username)
    elif result == ALREADY_OK:
        text_out = text(locale, "restore.already_ok", username=username)
    elif result == WEBHOOK_PENDING:
        # токен уже заменён: сказать «не вышло» было бы враньём, продавец
        # пошёл бы искать старый токен, которого больше нет
        text_out = text(locale, "restore.webhook_pending", username=username)
    elif result == NOT_MANAGED:
        text_out = text(locale, "restore.not_managed", username=username)
    else:
        text_out = text(locale, "restore.failed", username=username)

    kb = InlineKeyboardBuilder()
    kb.button(text=text(locale, "btn.back_all"), callback_data="mybots:menu")
    await callback.message.answer(text_out, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("mybots:back:"))
async def back_to_card(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    await callback.answer()
    bot = await get_own_bot(bot_id, seller.id)
    if callback.message and bot is not None:
        await callback.message.edit_text(
            bot_card_text(bot, seller_locale(seller)),
            reply_markup=bot_card_keyboard(bot, seller_locale(seller)),
        )
