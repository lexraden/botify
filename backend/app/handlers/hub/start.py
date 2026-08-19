"""Hub-бот: точка входа для продавцов. Регистрирует продавца и ведёт в онбординг."""

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.models import Seller, SellerBot

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


def new_seller_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧭 Пройти настройку", callback_data="onboarding:begin")
    return kb.as_markup()


def returning_seller_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    webapp_url = get_settings().effective_webapp_url
    if webapp_url:
        kb.button(
            text="🚀 Открыть кабинет продавца",
            web_app=types.WebAppInfo(url=webapp_url),
        )
    kb.button(text="🤖 Мои боты", callback_data="mybots:list")
    kb.button(text="➕ Подключить ещё бота", callback_data="onboarding:add_bot")
    kb.adjust(1)
    return kb.as_markup()


def welcome_back_text(bots: list[SellerBot]) -> str:
    active = [b for b in bots if b.is_active]
    if len(active) == 1:
        status = f"Твой бот <b>@{active[0].bot_username}</b> работает 🟢"
    elif active:
        status = f"Подключено ботов: <b>{len(active)}</b> 🟢"
    else:
        status = "Все твои боты сейчас отключены ⚪"
    return f"👋 С возвращением!\n\n{status}"


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
            bots: list[SellerBot] = []
        else:
            # обновляем то, что могло поменяться
            seller.username = tg_user.username
            seller.first_name = tg_user.first_name
            bots = (
                (
                    await session.execute(
                        select(SellerBot).where(SellerBot.seller_id == seller.id)
                    )
                )
                .scalars()
                .all()
            )
        await session.commit()

    if bots:
        await message.answer(welcome_back_text(bots), reply_markup=returning_seller_keyboard())
    else:
        await message.answer(WELCOME, reply_markup=new_seller_keyboard())
