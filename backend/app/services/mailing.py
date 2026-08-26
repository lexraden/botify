"""Рассылки по базе seller-бота (перенос идеи из reference/botconnect mailing.py).

Лимиты Telegram: ~30 сообщений/сек на бота. Держимся заметно ниже —
пауза 0.06с между отправками (~16/сек), чтобы не ловить 429."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, update
from sqlalchemy.sql import func

from app.bots.runner import make_seller_bot
from app.config import get_settings
from app.db import get_session
from app.models import Customer, Mailing, SellerBot
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)

SEND_DELAY_SEC = 0.06
# Как часто идущая рассылка отмечается живой. 200 сообщений — это ~12 секунд
# отправки: на порог оживления (10 минут) запас огромный, а запись в БД редкая.
HEARTBEAT_EVERY = 200


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
            # признак жизни: по нему застрявшую рассылку отличают от идущей
            mailing.heartbeat_at = func.now()
        await session.commit()
        mailing_ids = [m.id for m in due]

    for mailing_id in mailing_ids:
        try:
            await send_mailing(mailing_id)
        except Exception:
            logger.exception("Рассылка %s упала", mailing_id)


async def revive_stuck_mailings() -> int:
    """Возвращает в очередь рассылки, застрявшие в `sending`.

    Статус `sending` ставится перед отправкой, чтобы параллельный тик не
    подхватил рассылку второй раз. Но если процесс умрёт посреди отправки
    (деплой, OOM, рестарт контейнера), рассылка останется `sending` навсегда:
    цикл её больше не берёт, а в кабинете она выглядит вечно идущей.

    Возвращаем такие в `pending` — следующий тик отправит их заново. Повтор
    для части покупателей возможен, и это осознанный выбор: получить сообщение
    дважды неприятно, не получить вовсе — хуже, а точку обрыва мы не знаем.
    Живая рассылка под раздачу не попадает: `heartbeat_at` обновляется по ходу
    отправки (см. HEARTBEAT_EVERY), поэтому длинная рассылка по большой базе
    остаётся свежей всё время работы.
    """
    minutes = get_settings().mailing_stuck_minutes
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

    async with get_session() as session:
        stuck = list(
            (
                await session.execute(
                    select(Mailing).where(
                        Mailing.status == "sending",
                        # heartbeat_at нет у рассылок, начатых до появления
                        # колонки — для них ориентир created_at
                        func.coalesce(Mailing.heartbeat_at, Mailing.created_at) < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        for mailing in stuck:
            mailing.status = "pending"
            mailing.heartbeat_at = None
        await session.commit()

    if stuck:
        logger.warning(
            "Возвращено в очередь застрявших рассылок: %d (id: %s)",
            len(stuck),
            ", ".join(str(m.id) for m in stuck),
        )
    return len(stuck)


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
        for index, customer in enumerate(customers, start=1):
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
            if index % HEARTBEAT_EVERY == 0:
                await _touch_heartbeat(mailing_id)
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


async def _touch_heartbeat(mailing_id: int) -> None:
    """Отметить идущую рассылку живой (см. revive_stuck_mailings).

    Сбой отметки саму отправку ронять не должен: худшее, что случится, —
    рассылку сочтут застрявшей и отправят заново.
    """
    try:
        async with get_session() as session:
            await session.execute(
                update(Mailing).where(Mailing.id == mailing_id).values(heartbeat_at=func.now())
            )
            await session.commit()
    except Exception:
        logger.exception("Не удалось отметить рассылку %s живой", mailing_id)
