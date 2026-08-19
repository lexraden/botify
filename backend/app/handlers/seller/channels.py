"""Seller-бот в каналах продавца: регистрация канала, авто-приём заявок."""

import logging

from aiogram import Bot, Router
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatJoinRequest, ChatMemberUpdated

from app.db import get_session
from app.models import Seller, SellerBot
from app.services.channels import (
    TgUserInfo,
    deactivate_channel,
    get_channel,
    register_channel,
    upsert_customer,
)

logger = logging.getLogger(__name__)

router = Router(name=__name__)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_bot_added_to_chat(event: ChatMemberUpdated, bot: Bot, bot_record: SellerBot) -> None:
    if event.chat.type == "private":
        return
    channel, is_new = await register_channel(
        bot_record, event.chat.id, event.chat.title or "Без названия"
    )
    if not is_new:
        return

    # Продавец живёт в hub-боте — уведомляем его там
    from app.bots.hub import hub_bot

    async with get_session() as session:
        seller = await session.get(Seller, bot_record.seller_id)
    if seller is None:
        return
    try:
        await hub_bot.send_message(
            seller.telegram_id,
            f"✅ Бот @{bot_record.bot_username} добавлен в «{channel.title}».\n"
            "Заявки на вступление будут приниматься автоматически, а каждый "
            "вступивший — попадать в твою базу.",
        )
    except Exception:
        logger.exception("Не удалось уведомить продавца %s о новом канале", seller.id)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def on_bot_removed_from_chat(
    event: ChatMemberUpdated, bot: Bot, bot_record: SellerBot
) -> None:
    if event.chat.type == "private":
        return
    await deactivate_channel(event.chat.id)


@router.chat_join_request()
async def on_join_request(event: ChatJoinRequest, bot: Bot, bot_record: SellerBot) -> None:
    channel = await get_channel(event.chat.id)
    if channel is None or not channel.is_active or not channel.auto_accept:
        return

    # Лид попадает в базу продавца с источником-каналом
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

    # Приветствие в ЛС (сработает, если юзер уже писал боту; иначе Telegram не даст)
    greeting = channel.greeting_text or f"Добро пожаловать в «{channel.title}»!"
    try:
        await bot.send_message(event.from_user.id, greeting)
    except Exception:
        logger.info("ЛС для %s недоступна (юзер не стартовал бота)", event.from_user.id)
