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
    "👋 Добро пожаловать в <b>Botify</b>!\n\n"
    "Продавай товары и услуги через <b>своего Telegram-бота</b>, под своим брендом.\n\n"
    "✨ <b>Что умеет Botify:</b>\n\n"
    "🤖 <b>Свой бот</b> — под твоим именем, за пару минут\n"
    "🛍️ <b>Товары и услуги</b> — свой каталог, под себя\n"
    "💎 <b>Оплата в крипте</b> — принимай платежи прямо в Telegram\n"
    "👥 <b>Своя база клиентов</b> — покупатели и лиды сохраняются автоматически\n"
    "📢 <b>Рассылки</b> — не теряй клиентов, делай повторные продажи\n\n"
    "Всё в одном месте. <b>Просто. Быстро.</b>\n\n"
    "👇 Начнём настройку?"
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
