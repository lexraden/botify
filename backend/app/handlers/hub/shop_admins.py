"""Администраторы магазина: выдача роли в карточке и меню приглашённых.

Две стороны одной функции:

1. Владелец в карточке своего магазина («👥 Администраторы») приглашает
   админа по @username или Telegram ID и убирает лишних. Кандидат должен
   быть известен платформе — нажать /start у hub-бота: без записи в sellers
   платформа не сможет ни пустить его в кабинет, ни показать ему меню.
2. Приглашённый находит магазины кнопкой «Магазины, где я администратор»
   в /start и ведёт их в том же Mini App кабинете — наравне с владельцем,
   кроме денег (гард _require_owner в app/api/seller.py).

Каждое изменение состава уведомляет вторую сторону: владелец видит результат
в чате, новый (или убранный) админ получает пуш от hub-бота.
"""

import html
import re
from time import time

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from app.config import get_settings
from app.db import get_session
from app.handlers.hub.mybots import owned_bot_from_callback, shop_label
from app.models import Seller, SellerBot, StoreAdmin

router = Router()

# Состояние «жду @username или ID» живёт в памяти до перезапуска, поэтому
# ограничиваем по времени — как название магазина в /newshop
CONTACT_TIMEOUT_SEC = 15 * 60

# Telegram-юзернейм: 5–32 символа [A-Za-z0-9_]; с собачкой или без
USERNAME_RE = re.compile(r"^@?([A-Za-z0-9_]{5,32})$")

NO_SELLER = "Сначала нажми /start — я заведу тебя в системе."

ADMIN_POWERS_NOTE = (
    "Админ ведёт товары, заказы, отзывы и рассылки наравне с владельцем. "
    "Деньги выводит только владелец."
)


class AdminContact(StatesGroup):
    waiting_contact = State()


# --------------------------------------------------------------------------
# Приглашённая сторона: «Магазины, где я администратор»
# --------------------------------------------------------------------------


async def admin_bots_of(seller_id: int) -> list[SellerBot]:
    async with get_session() as session:
        bots = (
            (
                await session.execute(
                    select(SellerBot)
                    .join(StoreAdmin, StoreAdmin.bot_id == SellerBot.id)
                    .where(StoreAdmin.seller_id == seller_id)
                    .order_by(SellerBot.id)
                )
            )
            .scalars()
            .all()
        )
    return list(bots)


async def has_admin_shops(seller_id: int) -> bool:
    """Есть ли у продавца магазины с выданной ему ролью — для кнопки в /start."""
    async with get_session() as session:
        row = await session.execute(
            select(StoreAdmin.id).where(StoreAdmin.seller_id == seller_id).limit(1)
        )
        return row.scalar() is not None


def admin_shops_keyboard(bots: list[SellerBot]) -> types.InlineKeyboardMarkup | None:
    """Кнопка на каждый магазин — сразу в кабинет этого магазина."""
    webapp_url = get_settings().effective_webapp_url
    if not webapp_url or not bots:
        return None
    kb = InlineKeyboardBuilder()
    for bot in bots:
        kb.button(
            text=f"🏪 {shop_label(bot)}",
            web_app=types.WebAppInfo(url=f"{webapp_url.rstrip('/')}/shop/{bot.id}"),
        )
    kb.adjust(1)
    return kb.as_markup()


NO_ADMIN_SHOPS = (
    "Ты пока не администратор ни одного магазина.\n\n"
    "Владелец магазина выдаёт доступ в карточке своего магазина — по твоему "
    "@username в Botify."
)


async def _send_admin_shops_menu(target: types.Message, seller_id: int) -> None:
    """Список магазинов с ролью. seller_id — PK из sellers: у
    callback.message.from_user это бот, а не нажавший кнопку человек."""
    bots = await admin_bots_of(seller_id)
    if not bots:
        await target.answer(NO_ADMIN_SHOPS)
        return
    header = "🛠 <b>Магазины, где ты администратор</b>\n\n"
    await target.answer(
        header + "\n".join(f"• {shop_label(bot)}" for bot in bots),
        reply_markup=admin_shops_keyboard(bots),
    )


async def _seller_for(telegram_id: int) -> Seller | None:
    async with get_session() as session:
        return (
            await session.execute(select(Seller).where(Seller.telegram_id == telegram_id))
        ).scalar_one_or_none()


@router.message(Command("adminshops"))
async def cmd_adminshops(message: types.Message) -> None:
    if message.from_user is None:
        return
    seller = await _seller_for(message.from_user.id)
    if seller is None:
        await message.answer(NO_SELLER)
        return
    await _send_admin_shops_menu(message, seller.id)


@router.callback_query(F.data == "adminshops:list")
async def admin_shops_button(callback: types.CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    seller = await _seller_for(callback.from_user.id)
    if seller is None:
        await callback.message.answer(NO_SELLER)
        return
    await _send_admin_shops_menu(callback.message, seller.id)


# --------------------------------------------------------------------------
# Владелец: список админов в карточке магазина
# --------------------------------------------------------------------------


async def _admins_of(bot_id: int) -> list[tuple[StoreAdmin, Seller]]:
    async with get_session() as session:
        rows = (
            await session.execute(
                select(StoreAdmin, Seller)
                .join(Seller, Seller.id == StoreAdmin.seller_id)
                .where(StoreAdmin.bot_id == bot_id)
                .order_by(StoreAdmin.id)
            )
        ).all()
    return [(admin, seller) for admin, seller in rows]


def admin_display_name(seller: Seller) -> str:
    return f"@{seller.username}" if seller.username else (seller.first_name or "без имени")


def admins_menu_text(bot: SellerBot, admins: list[tuple[StoreAdmin, Seller]]) -> str:
    lines = (
        "\n".join(f"• {admin_display_name(seller)}" for _, seller in admins)
        if admins
        else "Пока никого — магазин ведёшь только ты."
    )
    return (
        f"👥 <b>Администраторы {shop_label(bot)}</b>\n\n{lines}\n\n{ADMIN_POWERS_NOTE}"
    )


def admins_menu_keyboard(bot_id: int, admins: list[tuple[StoreAdmin, Seller]]):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить админа", callback_data=f"mybots:adm_add:{bot_id}")
    for admin, seller in admins:
        kb.button(
            text=f"✖️ {admin_display_name(seller)}",
            callback_data=f"mybots:adm_del:{bot_id}:{seller.id}",
        )
    kb.button(text="⬅️ К магазину", callback_data=f"mybots:back:{bot_id}")
    kb.adjust(1)
    return kb.as_markup()


async def _show_admins(message: types.Message, bot: SellerBot) -> None:
    admins = await _admins_of(bot.id)
    await message.edit_text(admins_menu_text(bot, admins), reply_markup=admins_menu_keyboard(bot.id, admins))


@router.callback_query(F.data.startswith("mybots:admins:"))
async def open_admins(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    _, bot_id = ctx
    await callback.answer()
    bot = await _bot_by_id(bot_id)
    if callback.message is not None and bot is not None:
        await _show_admins(callback.message, bot)


async def _bot_by_id(bot_id: int) -> SellerBot | None:
    async with get_session() as session:
        return await session.get(SellerBot, bot_id)


# --------------------------------------------------------------------------
# Владелец: приглашение админа — @username или числовой ID
# --------------------------------------------------------------------------


@router.callback_query(F.data.startswith("mybots:adm_add:"))
async def ask_admin_contact(callback: types.CallbackQuery, state: FSMContext) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    _, bot_id = ctx
    await callback.answer()
    bot = await _bot_by_id(bot_id)
    if bot is None or callback.message is None:
        return
    await state.set_state(AdminContact.waiting_contact)
    await state.update_data(bot_id=bot_id, asked_at=time())
    await callback.message.answer(
        f"Кого сделать администратором <b>{shop_label(bot)}</b>?\n\n"
        "Пришли @username или числовой ID.\n\n"
        "Человек должен быть зарегистрирован в Botify — хоть раз нажать /start "
        "в этом боте. Иначе я его не знаю и добавить не смогу.\n\n"
        f"{ADMIN_POWERS_NOTE}.",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.message(StateFilter(AdminContact.waiting_contact), F.text)
async def got_admin_contact(message: types.Message, state: FSMContext) -> None:
    seller = None
    if message.from_user is not None:
        async with get_session() as session:
            seller = (
                await session.execute(
                    select(Seller).where(Seller.telegram_id == message.from_user.id)
                )
            ).scalar_one_or_none()
    if seller is None:
        await state.clear()
        await message.answer(NO_SELLER)
        return

    data = await state.get_data()
    if time() - data.get("asked_at", 0) > CONTACT_TIMEOUT_SEC:
        # разговор давно прервали: следующая реплика — не ответ на вопрос
        await state.clear()
        return

    contact = (message.text or "").strip()
    if contact.startswith("/"):
        await state.clear()
        await message.answer("Ок, отложим. Захочешь — кнопка «Администраторы» в карточке магазина.")
        return

    bot = await _bot_by_id(int(data.get("bot_id", 0)))
    if bot is None or bot.seller_id != seller.id:
        await state.clear()
        await message.answer("Магазин не найден.")
        return

    candidate = None
    async with get_session() as session:
        if contact.isdigit():
            candidate = (
                await session.execute(select(Seller).where(Seller.telegram_id == int(contact)))
            ).scalar_one_or_none()
        else:
            match = USERNAME_RE.match(contact)
            if match is None:
                await message.answer(
                    "Не похоже на @username или ID. Юзернейм — от 5 символов: "
                    "буквы, цифры и подчёркивания."
                )
                return
            username = match.group(1).lower()
            # Telegram-юзернеймы нечувствительны к регистру, а в БД они лежат
            # как пришли от Telegram — сравниваем в нижнем регистре
            candidate = (
                await session.execute(
                    select(Seller).where(func.lower(Seller.username) == username)
                )
            ).scalar_one_or_none()

    if candidate is None:
        await message.answer(
            "Никого такого в Botify нет.\n\n"
            "Человек должен был хоть раз нажать /start в этом боте — проверь "
            "написание. Если он заходил без юзернейма, попроси у него числовой ID."
        )
        return
    if candidate.id == bot.seller_id:
        await message.answer("Это ты и есть — владелец магазина 🙂")
        return

    async with get_session() as session:
        existing = (
            await session.execute(
                select(StoreAdmin).where(
                    StoreAdmin.bot_id == bot.id, StoreAdmin.seller_id == candidate.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            await message.answer("Он уже администратор этого магазина.")
            return
        session.add(StoreAdmin(bot_id=bot.id, seller_id=candidate.id))
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ {html.escape(admin_display_name(candidate))} теперь администратор "
        f"{shop_label(bot)}.\n\nЯ написал ему — магазин появится в его /start.",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    await notify_admin_assigned(bot, candidate)


def shop_owner_id(bot: SellerBot) -> int:
    return bot.seller_id


async def notify_admin_assigned(bot: SellerBot, candidate: Seller) -> None:
    """Новому админу: что случилось и где искать магазин."""
    from app.bots.hub import hub_bot

    kb = InlineKeyboardBuilder()
    kb.button(text="🛠 Магазины, где я админ", callback_data="adminshops:list")
    kb.adjust(1)
    try:
        await hub_bot.send_message(
            candidate.telegram_id,
            f"🛠 Тебе выдали права администратора магазина "
            f"<b>{html.escape(shop_label(bot))}</b>.\n\n{ADMIN_POWERS_NOTE}.\n\n"
            "Кнопка «Магазины, где я администратор» появится у тебя в /start.",
            reply_markup=kb.as_markup(),
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Не удалось уведомить нового админа %s о магазине %s", candidate.id, bot.id
        )


# --------------------------------------------------------------------------
# Владелец: убрать админа — с подтверждением
# --------------------------------------------------------------------------


@router.callback_query(F.data.startswith("mybots:adm_del:"))
async def confirm_remove_admin(callback: types.CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        return
    # здесь в callback два id, поэтому гард владения вручную, а не через
    # owned_bot_from_callback (он берёт последний сегмент как bot_id)
    bot_id, admin_seller_id = int(parts[2]), int(parts[3])
    if callback.from_user is None:
        return
    async with get_session() as session:
        seller = (
            await session.execute(
                select(Seller).where(Seller.telegram_id == callback.from_user.id)
            )
        ).scalar_one_or_none()
        bot = await session.get(SellerBot, bot_id)
    if seller is None:
        await callback.answer("Сначала /start", show_alert=True)
        return
    if bot is None or bot.seller_id != seller.id:
        await callback.answer("Бот не найден", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(
        text="Убрать", callback_data=f"mybots:adm_del_yes:{bot_id}:{admin_seller_id}"
    )
    kb.button(text="Отмена", callback_data=f"mybots:admins:{bot_id}")
    kb.adjust(1)
    await callback.answer()
    admin = await _seller_by_id(admin_seller_id)
    if callback.message is not None:
        name = admin_display_name(admin) if admin is not None else "этого человека"
        await callback.message.edit_text(
            f"Убрать <b>{html.escape(name)}</b> "
            f"из администраторов {shop_label(bot)}? Он потеряет доступ к кабинету магазина.",
            reply_markup=kb.as_markup(),
        )


async def _seller_by_id(seller_id: int) -> Seller | None:
    async with get_session() as session:
        return await session.get(Seller, seller_id)


@router.callback_query(F.data.startswith("mybots:adm_del_yes:"))
async def do_remove_admin(callback: types.CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or callback.from_user is None:
        return
    bot_id, admin_seller_id = int(parts[2]), int(parts[3])
    async with get_session() as session:
        seller = (
            await session.execute(
                select(Seller).where(Seller.telegram_id == callback.from_user.id)
            )
        ).scalar_one_or_none()
        bot = await session.get(SellerBot, bot_id)
    if seller is None:
        await callback.answer("Сначала /start", show_alert=True)
        return
    if bot is None or bot.seller_id != seller.id:
        await callback.answer("Бот не найден", show_alert=True)
        return

    async with get_session() as session:
        row = (
            await session.execute(
                select(StoreAdmin).where(
                    StoreAdmin.bot_id == bot_id, StoreAdmin.seller_id == admin_seller_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            await callback.answer("Уже убран", show_alert=True)
            bot = await session.get(SellerBot, bot_id)
            if callback.message is not None and bot is not None:
                await _show_admins(callback.message, bot)
            return
        await session.delete(row)
        await session.commit()

    await callback.answer("Убран")
    if callback.message is not None:
        bot = await _bot_by_id(bot_id)
        if bot is not None:
            await _show_admins(callback.message, bot)
    removed = await _seller_by_id(admin_seller_id)
    if removed is not None:
        await notify_admin_removed(bot, removed)


async def notify_admin_removed(bot: SellerBot, admin: Seller) -> None:
    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(
            admin.telegram_id,
            f"Тебя убрали из администраторов магазина "
            f"<b>{html.escape(shop_label(bot))}</b> — доступ к его кабинету закрыт.",
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Не удалось уведомить убранного админа %s о магазине %s", admin.id, bot.id
        )
