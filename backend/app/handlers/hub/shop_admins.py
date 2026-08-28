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
в чате, новый (или убранный) админ получает пуш от hub-бота. Все тексты —
на языке получателя (services/seller_texts.py).
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
from app.services.seller_texts import seller_locale, seller_text, text

router = Router()

# Состояние «жду @username или ID» живёт в памяти до перезапуска, поэтому
# ограничиваем по времени — как название магазина в /newshop
CONTACT_TIMEOUT_SEC = 15 * 60

# Telegram-юзернейм: 5–32 символа [A-Za-z0-9_]; с собачкой или без
USERNAME_RE = re.compile(r"^@?([A-Za-z0-9_]{5,32})$")


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


async def _send_admin_shops_menu(target: types.Message, seller: Seller) -> None:
    """Список магазинов с ролью. seller — строка из sellers: у
    callback.message.from_user это бот, а не нажавший кнопку человек."""
    bots = await admin_bots_of(seller.id)
    locale = seller_locale(seller)
    if not bots:
        await target.answer(text(locale, "admins.none_shops"))
        return
    header = text(locale, "admins.header") + "\n\n"
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
        await message.answer(text("ru", "hub.no_seller"))
        return
    await _send_admin_shops_menu(message, seller)


@router.callback_query(F.data == "adminshops:list")
async def admin_shops_button(callback: types.CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    seller = await _seller_for(callback.from_user.id)
    if seller is None:
        await callback.message.answer(text("ru", "hub.no_seller"))
        return
    await _send_admin_shops_menu(callback.message, seller)


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


def admin_display_name(seller: Seller | None, locale: str = "ru") -> str:
    if seller is None:
        return text(locale, "admins.name_fallback")
    if seller.username:
        return f"@{seller.username}"
    return seller.first_name or text(locale, "admins.nameless")


def admins_menu_text(
    bot: SellerBot, admins: list[tuple[StoreAdmin, Seller]], locale: str = "ru"
) -> str:
    lines = (
        "\n".join(f"• {admin_display_name(seller, locale)}" for _, seller in admins)
        if admins
        else text(locale, "admins.menu_empty")
    )
    return (
        f"{text(locale, 'admins.menu_title', label=shop_label(bot))}\n\n{lines}\n\n"
        f"{text(locale, 'admins.note')}"
    )


def admins_menu_keyboard(
    bot_id: int, admins: list[tuple[StoreAdmin, Seller]], locale: str = "ru"
):
    kb = InlineKeyboardBuilder()
    kb.button(text=text(locale, "btn.add_admin"), callback_data=f"mybots:adm_add:{bot_id}")
    for admin, seller in admins:
        kb.button(
            text=f"✖️ {admin_display_name(seller, locale)}",
            callback_data=f"mybots:adm_del:{bot_id}:{seller.id}",
        )
    kb.button(text=text(locale, "btn.back_to_shop"), callback_data=f"mybots:back:{bot_id}")
    kb.adjust(1)
    return kb.as_markup()


async def _show_admins(message: types.Message, bot: SellerBot, seller: Seller) -> None:
    admins = await _admins_of(bot.id)
    locale = seller_locale(seller)
    await message.edit_text(
        admins_menu_text(bot, admins, locale),
        reply_markup=admins_menu_keyboard(bot.id, admins, locale),
    )


@router.callback_query(F.data.startswith("mybots:admins:"))
async def open_admins(callback: types.CallbackQuery) -> None:
    ctx = await owned_bot_from_callback(callback)
    if ctx is None:
        return
    seller, bot_id = ctx
    await callback.answer()
    bot = await _bot_by_id(bot_id)
    if callback.message is not None and bot is not None:
        await _show_admins(callback.message, bot, seller)


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
    seller, bot_id = ctx
    locale = seller_locale(seller)
    await callback.answer()
    bot = await _bot_by_id(bot_id)
    if bot is None or callback.message is None:
        return
    await state.set_state(AdminContact.waiting_contact)
    await state.update_data(bot_id=bot_id, asked_at=time())
    await callback.message.answer(
        text(
            locale,
            "admins.ask_contact",
            label=shop_label(bot),
            note=text(locale, "admins.note"),
        ),
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
        await message.answer(text("ru", "hub.no_seller"))
        return
    locale = seller_locale(seller)

    data = await state.get_data()
    if time() - data.get("asked_at", 0) > CONTACT_TIMEOUT_SEC:
        # разговор давно прервали: следующая реплика — не ответ на вопрос
        await state.clear()
        return

    contact = (message.text or "").strip()
    if contact.startswith("/"):
        await state.clear()
        await message.answer(text(locale, "admins.cancel"))
        return

    bot = await _bot_by_id(int(data.get("bot_id", 0)))
    if bot is None or bot.seller_id != seller.id:
        await state.clear()
        await message.answer(text(locale, "admins.shop_not_found"))
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
                await message.answer(text(locale, "admins.bad_contact"))
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
        await message.answer(text(locale, "admins.unknown"))
        return
    if candidate.id == bot.seller_id:
        await message.answer(text(locale, "admins.is_owner"))
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
            await message.answer(text(locale, "admins.already"))
            return
        session.add(StoreAdmin(bot_id=bot.id, seller_id=candidate.id))
        await session.commit()

    await state.clear()
    await message.answer(
        text(
            locale,
            "admins.added",
            name=html.escape(admin_display_name(candidate, locale)),
            label=shop_label(bot),
        ),
        reply_markup=types.ReplyKeyboardRemove(),
    )
    await notify_admin_assigned(bot, candidate)


def shop_owner_id(bot: SellerBot) -> int:
    return bot.seller_id


async def notify_admin_assigned(bot: SellerBot, candidate: Seller) -> None:
    """Новому админу: что случилось и где искать магазин."""
    from app.bots.hub import hub_bot

    kb = InlineKeyboardBuilder()
    kb.button(
        text=seller_text(candidate, "admins.btn_push"), callback_data="adminshops:list"
    )
    kb.adjust(1)
    try:
        await hub_bot.send_message(
            candidate.telegram_id,
            seller_text(
                candidate,
                "push.admin_assigned",
                label=html.escape(shop_label(bot)),
                note=seller_text(candidate, "admins.note"),
            ),
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
        await callback.answer(text("ru", "alert.start_first"), show_alert=True)
        return
    if bot is None or bot.seller_id != seller.id:
        await callback.answer(text("ru", "alert.bot_not_found"), show_alert=True)
        return
    locale = seller_locale(seller)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=text(locale, "btn.remove"), callback_data=f"mybots:adm_del_yes:{bot_id}:{admin_seller_id}"
    )
    kb.button(text=text(locale, "btn.cancel"), callback_data=f"mybots:admins:{bot_id}")
    kb.adjust(1)
    await callback.answer()
    admin = await _seller_by_id(admin_seller_id)
    if callback.message is not None:
        name = admin_display_name(admin, locale)
        await callback.message.edit_text(
            text(
                locale,
                "admins.remove_confirm",
                name=html.escape(name),
                label=shop_label(bot),
            ),
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
        await callback.answer(text("ru", "alert.start_first"), show_alert=True)
        return
    if bot is None or bot.seller_id != seller.id:
        await callback.answer(text("ru", "alert.bot_not_found"), show_alert=True)
        return
    locale = seller_locale(seller)

    async with get_session() as session:
        row = (
            await session.execute(
                select(StoreAdmin).where(
                    StoreAdmin.bot_id == bot_id, StoreAdmin.seller_id == admin_seller_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            await callback.answer(text(locale, "toast.already_removed"), show_alert=True)
            bot = await session.get(SellerBot, bot_id)
            if callback.message is not None and bot is not None:
                await _show_admins(callback.message, bot, seller)
            return
        await session.delete(row)
        await session.commit()

    await callback.answer(text(locale, "toast.removed"))
    if callback.message is not None:
        bot = await _bot_by_id(bot_id)
        if bot is not None:
            await _show_admins(callback.message, bot, seller)
    removed = await _seller_by_id(admin_seller_id)
    if removed is not None:
        await notify_admin_removed(bot, removed)


async def notify_admin_removed(bot: SellerBot, admin: Seller) -> None:
    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(
            admin.telegram_id,
            seller_text(
                admin,
                "push.admin_removed",
                label=html.escape(shop_label(bot)),
            ),
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Не удалось уведомить убранного админа %s о магазине %s", admin.id, bot.id
        )
