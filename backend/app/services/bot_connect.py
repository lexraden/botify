"""Подключение бота продавца: валидация токена через getMe, шифрование, вебхук.

Шаг 3.5 онбординга из брифа (docs/project-brief.md, раздел 3.5).
"""

import logging
import re
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import exists, select

from app.bots.runner import remove_seller_webhook, setup_seller_webhook
from app.db import get_session
from app.models import Order, Seller, SellerBot
from app.security import encrypt_bot_token

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")


@dataclass
class ConnectResult:
    ok: bool
    error: str | None = None  # ключ ошибки для текста в хендлере
    bot_record: SellerBot | None = None
    bot_username: str | None = None


async def connect_seller_bot(seller_id: int, raw_token: str) -> ConnectResult:
    token = raw_token.strip()
    if not TOKEN_RE.match(token):
        return ConnectResult(ok=False, error="bad_format")

    # Валидация: токен рабочий и принадлежит реальному боту
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
    except Exception:
        return ConnectResult(ok=False, error="get_me_failed")
    finally:
        await bot.session.close()

    async with get_session() as session:
        existing = (
            await session.execute(
                select(SellerBot).where(SellerBot.telegram_bot_id == me.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.seller_id != seller_id:
                return ConnectResult(ok=False, error="taken_by_other")
            if existing.is_active:
                return ConnectResult(
                    ok=False, error="already_yours", bot_username=existing.bot_username
                )
            # переподключение ранее отключённого бота: обновляем токен и вебхук
            existing.bot_token_encrypted = encrypt_bot_token(token)
            existing.bot_username = me.username or str(me.id)
            existing.is_active = True
            webhook_ok = await setup_seller_webhook(existing)
            existing.webhook_status = "active" if webhook_ok else "pending"
            await session.commit()
            return ConnectResult(ok=True, bot_record=existing, bot_username=existing.bot_username)

        record = SellerBot(
            seller_id=seller_id,
            bot_token_encrypted=encrypt_bot_token(token),
            bot_username=me.username or str(me.id),
            telegram_bot_id=me.id,
            webhook_status="pending",
        )
        session.add(record)
        await session.flush()  # получаем record.id для пути вебхука

        webhook_ok = await setup_seller_webhook(record)
        record.webhook_status = "active" if webhook_ok else "pending"

        seller = await session.get(Seller, seller_id)
        if seller is not None:
            seller.onboarding_step = "bot_done"

        await session.commit()
        return ConnectResult(ok=True, bot_record=record, bot_username=record.bot_username)


async def get_own_bot(bot_id: int, seller_id: int) -> SellerBot | None:
    async with get_session() as session:
        bot = await session.get(SellerBot, bot_id)
        if bot is None or bot.seller_id != seller_id:
            return None
        return bot


async def disconnect_bot(bot_id: int, seller_id: int) -> SellerBot | None:
    """Отключает бота: снимает вебхук, is_active=False. Данные сохраняются."""
    async with get_session() as session:
        bot = await session.get(SellerBot, bot_id)
        if bot is None or bot.seller_id != seller_id:
            return None
        await remove_seller_webhook(bot)
        bot.is_active = False
        bot.webhook_status = "pending"
        await session.commit()
        return bot


async def enable_bot(bot_id: int, seller_id: int) -> SellerBot | None:
    """Включает ранее отключённого бота: is_active=True + вебхук."""
    async with get_session() as session:
        bot = await session.get(SellerBot, bot_id)
        if bot is None or bot.seller_id != seller_id:
            return None
        if bot.bot_token_encrypted is None:
            # черновик: включать нечего, магазин без бота покупателям не отдаётся
            return None
        bot.is_active = True
        webhook_ok = await setup_seller_webhook(bot)
        bot.webhook_status = "active" if webhook_ok else "pending"
        await session.commit()
        return bot


async def delete_bot(bot_id: int, seller_id: int) -> str:
    """Полное удаление бота вместе с его базой покупателей.

    Если у покупателей этого бота есть заказы — не удаляем (история продаж
    неприкосновенна), возвращаем 'has_orders': бот остаётся отключённым.
    Возвращает 'deleted' | 'has_orders' | 'not_found'.
    """
    async with get_session() as session:
        bot = await session.get(SellerBot, bot_id)
        if bot is None or bot.seller_id != seller_id:
            return "not_found"

        has_orders = (
            await session.execute(select(exists().where(Order.bot_id == bot_id)))
        ).scalar()
        if has_orders:
            await remove_seller_webhook(bot)
            bot.is_active = False
            bot.webhook_status = "pending"
            await session.commit()
            return "has_orders"

        await remove_seller_webhook(bot)
        # каскадом уходят покупатели, каталог и рассылки этого магазина
        await session.delete(bot)
        await session.commit()
        return "deleted"
