"""Подключение бота продавца: валидация токена через getMe, шифрование, вебхук.

Шаг 3.5 онбординга из брифа (docs/project-brief.md, раздел 3.5).
"""

import logging
import re
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import select

from app.bots.runner import setup_seller_webhook
from app.db import get_session
from app.models import Seller, SellerBot
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
            if existing.seller_id == seller_id:
                return ConnectResult(
                    ok=False, error="already_yours", bot_username=existing.bot_username
                )
            return ConnectResult(ok=False, error="taken_by_other")

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
            seller.onboarding_step = "done"

        await session.commit()
        return ConnectResult(ok=True, bot_record=record, bot_username=record.bot_username)
