"""Выбор языка hub-бота: команда /lang, кнопки RU/EN.

Язык пишется в sellers.locale и главнее Telegram-языка (правило целиком —
app/services/seller_texts.py). Команда не трогает FSM-состояния: если человек
переключает язык посреди диалога (/newshop, приглашение админа), диалог
продолжается дальше — /lang только меняет язык сообщений.

После выбора меню команд в чате продавца перезаписывается на его языке
(BotCommandScopeChat): у остальных продавцов остаётся дефолтный список.
"""

import logging

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.db import get_session
from app.models import Seller
from app.services.seller_texts import SELLER_LOCALES, seller_locale, seller_text

router = Router()

# Единый список для дефолтного скоупа (setup_hub_webhook) и пер-чатовых
# перезаписей: описания дефолта — русские, язык самого hub-бота исторический.
COMMANDS: dict[str, list[BotCommand]] = {
    "ru": [
        BotCommand(command="start", description="Начать / настройка"),
        BotCommand(command="mybots", description="Мои магазины"),
        BotCommand(command="adminshops", description="Магазины, где я админ"),
        BotCommand(command="newshop", description="Новый магазин"),
        BotCommand(command="lang", description="Язык / Language"),
    ],
    "en": [
        BotCommand(command="start", description="Start / setup"),
        BotCommand(command="mybots", description="My shops"),
        BotCommand(command="adminshops", description="Shops I administer"),
        BotCommand(command="newshop", description="New shop"),
        BotCommand(command="lang", description="Language / Язык"),
    ],
}


async def apply_chat_commands(locale: str, chat_id: int) -> None:
    """Перезаписать меню команд в чате продавца на выбранном языке.

    Ошибку глотаем: меню команд — украшение, а не критичный путь; упавший
    вызов не должен ломать переключение языка.
    """
    from app.bots.hub import hub_bot

    try:
        await hub_bot.set_my_commands(
            COMMANDS[locale], scope=BotCommandScopeChat(chat_id=chat_id)
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Не удалось записать меню команд на %s для чата %s", locale, chat_id
        )


def lang_keyboard() -> types.InlineKeyboardMarkup:
    from app.services.seller_texts import text

    kb = InlineKeyboardBuilder()
    kb.button(text=text("ru", "lang.btn.ru"), callback_data="lang:set:ru")
    kb.button(text=text("en", "lang.btn.en"), callback_data="lang:set:en")
    kb.adjust(1)
    return kb.as_markup()


async def _seller_for(telegram_id: int) -> Seller | None:
    async with get_session() as session:
        return (
            await session.execute(select(Seller).where(Seller.telegram_id == telegram_id))
        ).scalar_one_or_none()


@router.message(Command("lang"))
async def cmd_lang(message: types.Message) -> None:
    if message.from_user is None:
        return
    seller = await _seller_for(message.from_user.id)
    if seller is None:
        from app.services.seller_texts import text

        await message.answer(text("ru", "hub.no_seller"))
        return
    locale = seller_locale(seller)
    await message.answer(
        seller_text(seller, "lang.prompt", current=seller_text(seller, f"lang.name.{locale}")),
        reply_markup=lang_keyboard(),
    )


@router.callback_query(F.data.startswith("lang:set:"))
async def set_lang(callback: types.CallbackQuery) -> None:
    from app.services.seller_texts import text

    locale = (callback.data or "").split(":")[-1]
    if locale not in SELLER_LOCALES:
        await callback.answer()
        return
    if callback.from_user is None:
        return
    async with get_session() as session:
        seller = (
            await session.execute(
                select(Seller).where(Seller.telegram_id == callback.from_user.id)
            )
        ).scalar_one_or_none()
        if seller is None:
            await callback.answer(text("ru", "alert.start_first"), show_alert=True)
            return
        seller.locale = locale
        await session.commit()

    await callback.answer()
    # подтверждение — уже на выбранном языке
    if callback.message is not None:
        await callback.message.answer(text(locale, f"lang.done.{locale}"))
    await apply_chat_commands(locale, callback.from_user.id)
