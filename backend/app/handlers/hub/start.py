"""Hub-бот: точка входа для продавцов.

Онбординг целиком живёт в Mini App (см. docs/project-brief.md, п. 8.1),
поэтому бот только регистрирует продавца и открывает приложение. Тексты —
на языке продавца (services/seller_texts.py): выбор в /lang главнее,
без него ru* -> RU, остальным EN.
"""

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.handlers.hub.mybots import send_shops_menu
from app.handlers.hub.shop_admins import has_admin_shops
from app.models import Seller, SellerBot
from app.services.seller_texts import seller_locale, seller_text, text

router = Router()


def open_app_keyboard(
    with_bots: bool = False, admin_bots: bool = False, locale: str = "ru"
) -> types.InlineKeyboardMarkup | None:
    webapp_url = get_settings().effective_webapp_url
    if not webapp_url:
        return None
    kb = InlineKeyboardBuilder()
    kb.button(text=text(locale, "btn.open_app"), web_app=types.WebAppInfo(url=webapp_url))
    if with_bots:
        kb.button(text=text(locale, "btn.my_shops"), callback_data="mybots:list")
    if admin_bots:
        # пункт меню для приглашённых админов: ведёт к списку магазинов,
        # которые им доверили вести
        kb.button(text=text(locale, "btn.admin_shops"), callback_data="adminshops:list")
    kb.adjust(1)
    return kb.as_markup()


def welcome_back_text(bots: list[SellerBot], locale: str = "ru") -> str:
    # случай «все магазины отключены» в cmd_start уходит сразу в меню
    # магазинов, поэтому здесь всегда есть хоть один включённый
    active = [b for b in bots if b.is_active]
    if len(active) == 1:
        status = text(locale, "start.back_one", username=active[0].bot_username)
    else:
        status = text(locale, "start.back_many", n=len(active))
    return text(locale, "start.welcome_back", status=status)


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
            # объект нужен и после коммита: локаль определяет язык ответа
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

    admin_bots = await has_admin_shops(seller.id)
    keyboard = open_app_keyboard(
        with_bots=bool(bots), admin_bots=admin_bots, locale=seller_locale(seller)
    )
    if keyboard is None:
        await message.answer(seller_text(seller, "start.no_webapp"))
        return
    if bots and all(not b.is_active for b in bots):
        # все магазины отключены: открывать витрину нечего — сразу в меню
        # магазинов (включить этот или подключить ещё один)
        await send_shops_menu(message, seller)
        return
    # У продавца с подключёнными магазинами вместо вводного текста — короткий статус
    text_out = (
        welcome_back_text(bots, seller_locale(seller))
        if bots
        else seller_text(seller, "start.welcome")
    )
    await message.answer(text_out, reply_markup=keyboard)
