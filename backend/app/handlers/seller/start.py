"""Seller-бот: /start покупателя. Сбор базы с изоляцией по боту/продавцу."""

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.models import Customer, SellerBot

router = Router()


def catalog_keyboard(bot_record: SellerBot) -> types.InlineKeyboardMarkup | None:
    webapp_url = get_settings().webapp_url
    if not webapp_url:
        return None
    kb = InlineKeyboardBuilder()
    # Mini App получает контекст продавца через query-параметр;
    # витрина фильтрует каталог по этому bot_id (проверка — на бэкенде по initData)
    kb.button(
        text="🛍 Открыть каталог",
        web_app=types.WebAppInfo(url=f"{webapp_url}?bot_id={bot_record.id}"),
    )
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: types.Message, bot_record: SellerBot) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    # deep-link параметр /start <source> — источник/UTM
    source = None
    if message.text and " " in message.text:
        source = message.text.split(maxsplit=1)[1][:128]

    async with get_session() as session:
        result = await session.execute(
            select(Customer).where(
                Customer.telegram_id == tg_user.id,
                Customer.bot_id == bot_record.id,
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            session.add(
                Customer(
                    telegram_id=tg_user.id,
                    seller_id=bot_record.seller_id,
                    bot_id=bot_record.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    language_code=tg_user.language_code,
                    source=source,
                )
            )
            await session.commit()

    await message.answer(
        f"Добро пожаловать в магазин <b>@{bot_record.bot_username}</b>!",
        reply_markup=catalog_keyboard(bot_record),
    )
