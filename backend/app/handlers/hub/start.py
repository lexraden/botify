"""Hub-бот: точка входа для продавцов. Регистрирует продавца и ведёт в онбординг."""

from aiogram import Router, types
from aiogram.filters import CommandStart
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


def onboarding_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    webapp_url = get_settings().effective_webapp_url
    if webapp_url:
        kb.button(
            text="🚀 Открыть кабинет продавца",
            web_app=types.WebAppInfo(url=webapp_url),
        )
    kb.button(text="🧭 Пройти настройку", callback_data="onboarding:begin")
    kb.adjust(1)
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    async with get_session() as session:
        result = await session.execute(select(Seller).where(Seller.telegram_id == tg_user.id))
        seller = result.scalar_one_or_none()
        if seller is None:
            seller = Seller(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                language_code=tg_user.language_code,
                is_admin=tg_user.id in get_settings().admin_ids,
            )
            session.add(seller)
        else:
            # обновляем то, что могло поменяться
            seller.username = tg_user.username
            seller.first_name = tg_user.first_name
        await session.commit()

    await message.answer(WELCOME, reply_markup=onboarding_keyboard())
