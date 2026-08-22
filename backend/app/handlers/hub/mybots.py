"""Управление подключёнными ботами: /mybots, отключение/включение/удаление."""

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.models import Seller, SellerBot
from app.services.bot_connect import delete_bot, disconnect_bot, enable_bot, get_own_bot

router = Router()

STATUS_ICONS = {"active": "🟢", "pending": "🟡", "failed": "🔴"}


def bot_card_text(bot: SellerBot) -> str:
    if bot.is_active:
        icon = STATUS_ICONS.get(bot.webhook_status, "⚪")
        return f"{icon} <b>@{bot.bot_username}</b> — работает"
    return f"⚪ <b>@{bot.bot_username}</b> — отключён"


def bot_card_keyboard(bot: SellerBot) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if bot.is_active:
        kb.button(text="🔌 Отключить", callback_data=f"mybots:off:{bot.id}")
    else:
        kb.button(text="🔁 Включить", callback_data=f"mybots:on:{bot.id}")
        kb.button(text="🗑 Удалить", callback_data=f"mybots:del:{bot.id}")
    kb.adjust(2)
    return kb.as_markup()


def add_bot_keyboard() -> types.InlineKeyboardMarkup | None:
    """Кнопка «подключить ещё бота» — диплинк сразу на шаг подключения.

    Гард входа в вебаппе перехватывает только «/», поэтому прямой URL
    /onboarding/bot открывается без редиректа на другие экраны.
    """
    webapp_url = get_settings().effective_webapp_url
    if not webapp_url:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(
        text="➕ Подключить ещё бота",
        web_app=types.WebAppInfo(url=f"{webapp_url.rstrip('/')}/onboarding/bot"),
    )
    kb.adjust(1)
    return kb.as_markup()


async def _seller_for(telegram_id: int) -> Seller | None:
    async with get_session() as session:
        result = await session.execute(select(Seller).where(Seller.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def send_bot_cards(message: types.Message, seller: Seller) -> None:
    async with get_session() as session:
        bots = (
            (await session.execute(select(SellerBot).where(SellerBot.seller_id == seller.id)))
            .scalars()
            .all()
        )
    if not bots:
        await message.answer("У тебя пока нет подключённых ботов. Настройка: /start")
        return
    for bot in bots:
        await message.answer(bot_card_text(bot), reply_markup=bot_card_keyboard(bot))
    # отдельным сообщением после карточек: из «Моих ботов» можно сразу
    # подключить следующего бота — каждый будет отдельным магазином
    kb = add_bot_keyboard()
    if kb is not None:
        await message.answer(
            "Нужен ещё один магазин? Каждый бот живёт своей жизнью: свой каталог, "
            "свои покупатели, своя касса.",
            reply_markup=kb,
        )


@router.message(Command("mybots"))
async def my_bots(message: types.Message) -> None:
    if message.from_user is None:
        return
    seller = await _seller_for(message.from_user.id)
    if seller is None:
        await message.answer("Нажми /start, чтобы зарегистрироваться.")
        return
    await send_bot_cards(message, seller)


@router.callback_query(F.data == "mybots:list")
async def my_bots_button(callback: types.CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None or callback.message is None:
        return
    seller = await _seller_for(callback.from_user.id)
    if seller is None:
        await callback.message.answer("Нажми /start, чтобы зарегистрироваться.")
        return
    await send_bot_cards(callback.message, seller)


async def _owned_bot_from_callback(callback: types.CallbackQuery) -> tuple[Seller, int] | None:
    if callback.from_user is None or callback.data is None:
        return None
    seller = await _seller_for(callback.from_user.id)
    if seller is None:
        await callback.answer("Сначала /start", show_alert=True)
        return None
    bot_id = int(callback.data.split(":")[-1])
    if await get_own_bot(bot_id, seller.id) is None:
        await callback.answer("Бот не найден", show_alert=True)
        return None
    return seller, bot_id


@router.callback_query(F.data.startswith("mybots:off:"))
async def confirm_disconnect(callback: types.CallbackQuery) -> None:
    ctx = await _owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    await callback.answer()
    bot = await get_own_bot(bot_id, seller.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, отключить", callback_data=f"mybots:off_yes:{bot_id}")
    kb.button(text="Отмена", callback_data=f"mybots:back:{bot_id}")
    kb.adjust(2)
    if callback.message:
        await callback.message.edit_text(
            f"Отключить <b>@{bot.bot_username}</b>?\n\n"
            "Бот перестанет отвечать покупателям и принимать заявки в каналы. "
            "База покупателей, товары и заказы сохранятся — включить можно в любой момент.",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("mybots:off_yes:"))
async def do_disconnect(callback: types.CallbackQuery) -> None:
    ctx = await _owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    bot = await disconnect_bot(bot_id, seller.id)
    await callback.answer("Отключён")
    if callback.message and bot is not None:
        await callback.message.edit_text(bot_card_text(bot), reply_markup=bot_card_keyboard(bot))


@router.callback_query(F.data.startswith("mybots:on:"))
async def do_enable(callback: types.CallbackQuery) -> None:
    ctx = await _owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    bot = await enable_bot(bot_id, seller.id)
    await callback.answer("Включён")
    if callback.message and bot is not None:
        await callback.message.edit_text(bot_card_text(bot), reply_markup=bot_card_keyboard(bot))


@router.callback_query(F.data.startswith("mybots:del:"))
async def confirm_delete(callback: types.CallbackQuery) -> None:
    ctx = await _owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    await callback.answer()
    bot = await get_own_bot(bot_id, seller.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить навсегда", callback_data=f"mybots:del_yes:{bot_id}")
    kb.button(text="Отмена", callback_data=f"mybots:back:{bot_id}")
    kb.adjust(1)
    if callback.message:
        await callback.message.edit_text(
            f"Удалить <b>@{bot.bot_username}</b> навсегда?\n\n"
            "⚠️ Вместе с ботом удалится его база покупателей и история рассылок. "
            "Это необратимо.",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("mybots:del_yes:"))
async def do_delete(callback: types.CallbackQuery) -> None:
    ctx = await _owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    bot = await get_own_bot(bot_id, seller.id)
    result = await delete_bot(bot_id, seller.id)
    if callback.message is None:
        return
    if result == "deleted":
        await callback.answer("Удалён")
        await callback.message.edit_text(
            f"🗑 Бот <b>@{bot.bot_username}</b> удалён вместе с базой покупателей."
        )
    elif result == "has_orders":
        await callback.answer()
        await callback.message.edit_text(
            f"У покупателей <b>@{bot.bot_username}</b> есть заказы — историю продаж "
            "удалять нельзя, поэтому бот просто отключён. Подключить обратно: /mybots."
        )
    else:
        await callback.answer("Бот не найден", show_alert=True)


@router.callback_query(F.data.startswith("mybots:back:"))
async def back_to_card(callback: types.CallbackQuery) -> None:
    ctx = await _owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    await callback.answer()
    bot = await get_own_bot(bot_id, seller.id)
    if callback.message and bot is not None:
        await callback.message.edit_text(bot_card_text(bot), reply_markup=bot_card_keyboard(bot))
