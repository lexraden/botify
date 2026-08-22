"""Seller-бот: /start покупателя. Сама запись в базу происходит в
CustomerTrackerMiddleware — сюда апдейт приходит уже с сохранённым customer."""

import html

from aiogram import F, Router, types
from aiogram.filters import CommandObject, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_settings
from app.models import SellerBot

router = Router()

DEFAULT_BUTTON_TEXT = "🛍 Открыть каталог"

# Верификация вступившего в канал: reply-кнопка внизу чата (ставится при приёме
# заявки, см. handlers/seller/channels.py). Нажатие приходит обычным сообщением.
ROBOT_BUTTON_TEXT = "Я не робот 🤖"
ROBOT_CONFIRM_TEXTS = {"Я не робот", "Я не робот 🤖"}


def is_robot_confirm(text: str | None) -> bool:
    return (text or "").strip() in ROBOT_CONFIRM_TEXTS


def catalog_keyboard(bot_record: SellerBot) -> types.InlineKeyboardMarkup | None:
    webapp_url = get_settings().effective_webapp_url
    if not webapp_url or not bot_record.show_catalog_button:
        return None
    kb = InlineKeyboardBuilder()
    # Mini App получает контекст продавца через query-параметр;
    # витрина фильтрует каталог по этому bot_id (проверка — на бэкенде по initData)
    kb.button(
        text=bot_record.catalog_button_text or DEFAULT_BUTTON_TEXT,
        web_app=types.WebAppInfo(url=f"{webapp_url}?bot_id={bot_record.id}"),
    )
    return kb.as_markup()


def welcome_text_for(bot_record: SellerBot) -> str:
    return bot_record.welcome_text or (
        f"Добро пожаловать в магазин <b>@{bot_record.bot_username}</b>!"
    )


async def send_welcome(message: types.Message, bot_record: SellerBot) -> None:
    """Приветствие из настроек бота + кнопка витрины. Единственная точка
    ответа «как на /start» — её же использует подтверждение «Я не робот»."""
    kb = catalog_keyboard(bot_record)
    try:
        await message.answer(welcome_text_for(bot_record), reply_markup=kb)
    except Exception:
        # продавец мог сохранить текст с битым HTML — витрина не должна ломаться
        await message.answer(html.escape(welcome_text_for(bot_record)), reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(
    message: types.Message, command: CommandObject, bot_record: SellerBot
) -> None:
    # «⚙️ Настройки бота» в хаб-боте ведёт диплинком t.me/<bot>?start=settings —
    # владельцу открываем меню настроек вместо приветствия покупателя
    if command.args == "settings":
        from app.handlers.seller.settings import is_owner, show_settings_menu

        if await is_owner(bot_record, message.from_user):
            await show_settings_menu(message, bot_record)
            return

    await send_welcome(message, bot_record)


@router.message(F.text.func(is_robot_confirm))
async def robot_confirm(message: types.Message, bot_record: SellerBot) -> None:
    """«Я не робот» после заявки в канал — тот же ответ, что и на /start:
    приветствие и кнопка витрины берутся из одних и тех же настроек бота."""
    await send_welcome(message, bot_record)
