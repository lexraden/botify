"""Hub-бот: точка входа для продавцов.

Онбординг целиком живёт в Mini App (см. docs/project-brief.md, п. 8.1),
поэтому бот только регистрирует продавца и открывает приложение.
"""

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.models import Seller

router = Router()

WELCOME = (
    "👋 Привет! Это <b>Botify</b> — платформа для продажи товаров и услуг "
    "через собственного Telegram бота.\n\n"
    "Здесь ты можешь:\n"
    "• принимать оплату в <b>USDT</b>\n"
    "• подключить <b>своего бота</b>\n"
    "• добавить <b>товары и услуги</b> в каталог\n"
    "• собирать <b>базу покупателей</b> и делать рассылки\n\n"
    "Начнём с настройки — жми кнопку ниже"
)

NO_WEBAPP = (
    "⚠️ Приложение пока не настроено: у платформы не задан публичный адрес. "
    "Загляни позже."
)


def open_app_keyboard() -> types.InlineKeyboardMarkup | None:
    webapp_url = get_settings().effective_webapp_url
    if not webapp_url:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Открыть приложение", web_app=types.WebAppInfo(url=webapp_url))
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    await state.clear()

    async with get_session() as session:
        result = await session.execute(select(Seller).where(Seller.telegram_id == tg_user.id))
        seller = result.scalar_one_or_none()
        if seller is None:
            session.add(
                Seller(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    language_code=tg_user.language_code,
                    is_admin=tg_user.id in get_settings().admin_ids,
                )
            )
        else:
            # обновляем то, что могло поменяться
            seller.username = tg_user.username
            seller.first_name = tg_user.first_name
        await session.commit()

    keyboard = open_app_keyboard()
    if keyboard is None:
        await message.answer(NO_WEBAPP)
        return
    await message.answer(WELCOME, reply_markup=keyboard)
