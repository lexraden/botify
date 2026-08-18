"""Мультибот-раннер: держит N seller-ботов на вебхуках /webhook/seller/{bot_id}.

Архитектура перенесена из reference/botconnect (main.py + handlers_for_added_bots),
с двумя отличиями:
- в путях вебхуков суррогатный bot_id, а не токен;
- токены достаются из БД только в зашифрованном виде и расшифровываются в памяти.
"""

import logging

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.handlers.seller import start as seller_start
from app.models import SellerBot
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)

# Общий Dispatcher для всех seller-ботов (как dp_for_added_bots в botconnect)
seller_dp = Dispatcher()
seller_dp.include_router(seller_start.router)

SELLER_ALLOWED_UPDATES = [
    "message",
    "callback_query",
    "chat_join_request",
    "my_chat_member",
    "chat_member",
]


def seller_webhook_path(bot_id: int) -> str:
    return f"/webhook/seller/{bot_id}"


def make_seller_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def setup_seller_webhook(record: SellerBot) -> bool:
    """Ставит вебхук для одного seller-бота. Возвращает успех."""
    settings = get_settings()
    if not settings.webhook_base_url:
        return False
    token = decrypt_bot_token(record.bot_token_encrypted)
    bot = make_seller_bot(token)
    try:
        url = f"{settings.webhook_base_url}{seller_webhook_path(record.id)}"
        info = await bot.get_webhook_info()
        if info.url != url:
            await bot.set_webhook(
                url=url,
                secret_token=settings.telegram_webhook_secret,
                drop_pending_updates=True,
                allowed_updates=SELLER_ALLOWED_UPDATES,
            )
        return True
    except Exception:
        logger.exception("Не удалось поставить вебхук для seller-бота id=%s", record.id)
        return False
    finally:
        await bot.session.close()


async def setup_all_seller_webhooks() -> None:
    async with get_session() as session:
        result = await session.execute(
            select(SellerBot).where(SellerBot.is_active.is_(True))
        )
        records = result.scalars().all()
        for record in records:
            ok = await setup_seller_webhook(record)
            record.webhook_status = "active" if ok else "failed"
        await session.commit()


async def feed_seller_update(bot_id: int, update_data: dict) -> None:
    """Роутит апдейт seller-бота в общий Dispatcher с контекстом bot_id/seller_id."""
    async with get_session() as session:
        record = await session.get(SellerBot, bot_id)
    if record is None or not record.is_active:
        logger.warning("Апдейт для неизвестного/выключенного seller-бота id=%s", bot_id)
        return

    token = decrypt_bot_token(record.bot_token_encrypted)
    bot = make_seller_bot(token)
    try:
        update = types.Update(**update_data)
        # bot_record попадает в хендлеры как аргумент (aiogram workflow data)
        await seller_dp.feed_update(bot, update, bot_record=record)
    finally:
        await bot.session.close()
