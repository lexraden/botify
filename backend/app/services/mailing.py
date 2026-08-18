"""Рассылки по базе seller-бота (перенос идеи из reference/botconnect mailing.py).

Лимиты Telegram: ~30 сообщений/сек на бота. Держимся заметно ниже —
пауза 0.06с между отправками (~16/сек), чтобы не ловить 429."""

import asyncio
import logging

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.sql import func

from app.bots.runner import make_seller_bot
from app.db import get_session
from app.models import Customer, Mailing, SellerBot
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)

SEND_DELAY_SEC = 0.06


def _keyboard(mailing: Mailing) -> InlineKeyboardMarkup | None:
    if not (mailing.button_text and mailing.button_url):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=mailing.button_text, url=mailing.button_url)]]
    )


async def process_due_mailings() -> None:
    """Отправляет все созревшие рассылки. Вызывается из фонового цикла."""
    async with get_session() as session:
        due = (
            (
                await session.execute(
                    select(Mailing).where(
                        Mailing.status == "pending",
                        (Mailing.scheduled_at.is_(None)) | (Mailing.scheduled_at <= func.now()),
                    )
                )
            )
            .scalars()
            .all()
        )
        for mailing in due:
            mailing.status = "sending"  # чтобы параллельный тик не подхватил повторно
        await session.commit()
        mailing_ids = [m.id for m in due]

    for mailing_id in mailing_ids:
        try:
            await send_mailing(mailing_id)
        except Exception:
            logger.exception("Рассылка %s упала", mailing_id)


async def send_mailing(mailing_id: int) -> None:
    async with get_session() as session:
        mailing = await session.get(Mailing, mailing_id)
        if mailing is None:
            return
        bot_record = await session.get(SellerBot, mailing.bot_id)
        customers = (
            (
                await session.execute(
                    select(Customer).where(
                        Customer.bot_id == mailing.bot_id,
                        Customer.is_banned.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        token = decrypt_bot_token(bot_record.bot_token_encrypted)
        keyboard = _keyboard(mailing)
        text = mailing.text

    bot = make_seller_bot(token)
    sent = failed = 0
    blocked_ids: list[int] = []
    try:
        for customer in customers:
            try:
                await bot.send_message(customer.telegram_id, text, reply_markup=keyboard)
                sent += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                try:
                    await bot.send_message(customer.telegram_id, text, reply_markup=keyboard)
                    sent += 1
                except Exception:
                    failed += 1
            except TelegramForbiddenError:
                # юзер заблокировал бота — больше не шлём ему
                blocked_ids.append(customer.id)
                failed += 1
            except Exception:
                failed += 1
            await asyncio.sleep(SEND_DELAY_SEC)
    finally:
        await bot.session.close()

    async with get_session() as session:
        mailing = await session.get(Mailing, mailing_id)
        mailing.sent_count = sent
        mailing.failed_count = failed
        mailing.status = "done"
        if blocked_ids:
            blocked = (
                (await session.execute(select(Customer).where(Customer.id.in_(blocked_ids))))
                .scalars()
                .all()
            )
            for customer in blocked:
                customer.is_banned = True
        await session.commit()

    logger.info("Рассылка %s: отправлено %s, ошибок %s", mailing_id, sent, failed)
