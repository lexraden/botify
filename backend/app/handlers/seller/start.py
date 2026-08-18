"""Seller-бот: /start покупателя. Сама запись в базу происходит в
CustomerTrackerMiddleware — сюда апдейт приходит уже с сохранённым customer."""

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_settings
from app.models import SellerBot

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
        web_app=types.WebAppInfo(url=f"{get_settings().webapp_url}?bot_id={bot_record.id}"),
    )
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: types.Message, bot_record: SellerBot) -> None:
    await message.answer(
        f"Добро пожаловать в магазин <b>@{bot_record.bot_username}</b>!",
        reply_markup=catalog_keyboard(bot_record),
    )
