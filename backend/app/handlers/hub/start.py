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
from app.handlers.hub.mybots import send_shops_menu
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
    "Начни продавать — жми кнопку 👇"
)

NO_WEBAPP = (
    "⚠️ Приложение пока не настроено: у платформы не задан публичный адрес. "
    "Загляни позже."
)


WELCOME_BACK = "👋 С возвращением!\n\n{status}"


def open_app_keyboard(with_bots: bool = False) -> types.InlineKeyboardMarkup | None:
    webapp_url = get_settings().effective_webapp_url
    if not webapp_url:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Открыть приложение", web_app=types.WebAppInfo(url=webapp_url))
    if with_bots:
        kb.button(text="🏪 Мои магазины", callback_data="mybots:list")
    kb.adjust(1)
    return kb.as_markup()


def welcome_back_text(bots: list[SellerBot]) -> str:
    # случай «все магазины отключены» в cmd_start уходит сразу в меню
    # магазинов, поэтому здесь всегда есть хоть один включённый
    active = [b for b in bots if b.is_active]
    if len(active) == 1:
        status = f"Твой магазин <b>@{active[0].bot_username}</b> работает 🟢"
    else:
        status = f"Работает магазинов: <b>{len(active)}</b> 🟢"
    return WELCOME_BACK.format(status=status)


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    await state.clear()

    async with get_session() as session:
        result = await session.execute(select(Seller).where(Seller.telegram_id == tg_user.id))
        seller = result.scalar_one_or_none()
        bots: list[SellerBot] = []
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
            # права админа пересчитываем каждый раз: ADMIN_TELEGRAM_IDS могли
            # заполнить уже после первого /start этого аккаунта
            seller.is_admin = tg_user.id in get_settings().admin_ids
            bots = list(
                (
                    await session.execute(
                        select(SellerBot).where(SellerBot.seller_id == seller.id)
                    )
                )
                .scalars()
                .all()
            )
        await session.commit()

    keyboard = open_app_keyboard(with_bots=bool(bots))
    if keyboard is None:
        await message.answer(NO_WEBAPP)
        return
    if bots and all(not b.is_active for b in bots):
        # все магазины отключены: открывать витрину нечего — сразу в меню
        # магазинов (включить этот или подключить ещё один)
        await send_shops_menu(message, seller)
        return
    # У продавца с подключёнными магазинами вместо вводного текста — короткий статус
    text = welcome_back_text(bots) if bots else WELCOME
    await message.answer(text, reply_markup=keyboard)
