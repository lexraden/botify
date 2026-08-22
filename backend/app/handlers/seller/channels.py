"""Seller-бот в каналах продавца: регистрация канала, авто-приём заявок,
верификация вступившего («Я не робот») перед приветствием."""

import logging

from aiogram import Bot, F, Router, types
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatJoinRequest, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db import get_session
from app.models import Seller, SellerBot
from app.services.channels import (
    TgUserInfo,
    deactivate_channel,
    get_bot_channel,
    get_channel_for_bot,
    register_channel,
    upsert_customer,
)

logger = logging.getLogger(__name__)

router = Router(name=__name__)

VERIFY_BUTTON_TEXT = "✅ Я не робот"


def _can_invite_users(event: ChatMemberUpdated) -> bool:
    """Может ли бот приглашать: у владельца канала права подразумеваются,
    у админа смотрим флаг. None/нет атрибута — считаем что ок."""
    return getattr(event.new_chat_member, "can_invite_users", True) is not False


def _channel_texts(channel, bot_record: SellerBot, invite_ok: bool) -> tuple[str, str]:
    """(текст в hub-бот, текст в собственный бот продавца)."""
    hub_text = (
        f"✅ Бот @{bot_record.bot_username} добавлен в «{channel.title}».\n"
        "Заявки на вступление будут приниматься автоматически, а каждый "
        "вступивший — попадать в твою базу."
    )
    if invite_ok:
        own_text = (
            f"📢 Канал «{channel.title}» подключён к магазину @{bot_record.bot_username}!\n\n"
            "Заявки принимаю автоматически, каждого вступившего приветствую "
            "и записываю в твою базу покупателей."
        )
    else:
        own_text = (
            f"📢 Канал «{channel.title}» подключён к магазину @{bot_record.bot_username}.\n\n"
            "⚠️ Но без права «Приглашать пользователей» я не вижу заявки на вступление. "
            "Открой настройки канала → Администраторы → отметь это право — "
            "и канал заработает полностью."
        )
    return hub_text, own_text


async def _notify_seller_both_bots(
    bot: Bot, bot_record: SellerBot, seller: Seller, hub_text: str, own_text: str
) -> None:
    """Одно и то же событие — в оба чата продавца: hub-бот и сам магазин.
    Падение одного уведомления не мешает второму."""
    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(seller.telegram_id, hub_text)
    except Exception:
        logger.exception("Не удалось уведомить продавца %s в hub-боте", seller.id)
    try:
        await bot.send_message(seller.telegram_id, own_text)
    except Exception:
        # продавец ещё не стартовал своего бота — Telegram не даст написать первым
        logger.info("ЛС продавца %s в собственном боте недоступна", seller.id)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_bot_added_to_chat(event: ChatMemberUpdated, bot: Bot, bot_record: SellerBot) -> None:
    if event.chat.type == "private":
        return
    channel, is_new = await register_channel(
        bot_record, event.chat.id, event.chat.title or "Без названия"
    )
    if not is_new:
        return

    async with get_session() as session:
        seller = await session.get(Seller, bot_record.seller_id)
    if seller is None:
        return
    hub_text, own_text = _channel_texts(channel, bot_record, _can_invite_users(event))
    await _notify_seller_both_bots(bot, bot_record, seller, hub_text, own_text)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def on_bot_removed_from_chat(
    event: ChatMemberUpdated, bot: Bot, bot_record: SellerBot
) -> None:
    if event.chat.type == "private":
        return
    await deactivate_channel(event.chat.id)


@router.chat_join_request()
async def on_join_request(event: ChatJoinRequest, bot: Bot, bot_record: SellerBot) -> None:
    # заявка обрабатывается только для канала ЭТОГО бота
    channel = await get_channel_for_bot(bot_record.id, event.chat.id)
    if channel is None or not channel.is_active or not channel.auto_accept:
        return

    # Лид попадает в базу продавца с источником-каналом сразу по заявке
    await upsert_customer(
        bot_record,
        TgUserInfo(
            telegram_id=event.from_user.id,
            username=event.from_user.username,
            first_name=event.from_user.first_name,
            language_code=event.from_user.language_code,
        ),
        source=f"channel:{event.chat.id}",
    )

    try:
        await bot.approve_chat_join_request(chat_id=event.chat.id, user_id=event.from_user.id)
    except Exception:
        logger.exception(
            "Не удалось одобрить заявку user=%s в канал %s", event.from_user.id, event.chat.id
        )
        return

    # Вместо приветствия сразу — верификация: юзер жмёт кнопку в боте,
    # его telegram_id подтверждается, и только потом приходит приветствие
    kb = InlineKeyboardBuilder()
    kb.button(text=VERIFY_BUTTON_TEXT, callback_data=f"verify:{channel.id}")
    kb.adjust(1)
    try:
        await bot.send_message(
            event.from_user.id,
            f"Заявка в «{channel.title}» принята ✅\n\n"
            "Нажми кнопку ниже, чтобы подтвердить, что ты не робот 👇",
            reply_markup=kb.as_markup(),
        )
    except Exception:
        logger.info("ЛС для %s недоступна (юзер не стартовал бота)", event.from_user.id)


def _greeting_for(channel) -> str:
    return channel.greeting_text or f"Добро пожаловать в «{channel.title}»!"


@router.callback_query(F.data.startswith("verify:"))
async def on_verify(
    callback: types.CallbackQuery, bot: Bot, bot_record: SellerBot
) -> None:
    try:
        channel_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ссылка устарела", show_alert=True)
        return
    # изоляция: кнопка сработает только для канала ЭТОГО бота
    channel = await get_bot_channel(bot_record.id, channel_id)
    if channel is None or not channel.is_active:
        await callback.answer("Канал больше не активен", show_alert=True)
        return

    user = callback.from_user
    # колбэки не проходят CustomerTrackerMiddleware — пишем сами
    await upsert_customer(
        bot_record,
        TgUserInfo(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            language_code=user.language_code,
        ),
        source=f"channel:{channel.telegram_chat_id}",
    )

    await callback.answer("Спасибо! ✅")
    greeting = _greeting_for(channel)
    try:
        # правкой убираем кнопку — повторное нажатие невозможно
        await callback.message.edit_text(greeting)
    except Exception:
        try:
            await bot.send_message(user.id, greeting)
        except Exception:
            logger.info("Приветствие для %s не доставлено", user.id)
