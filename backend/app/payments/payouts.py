"""Выплаты продавцам через Crypto Pay transfer.

Деньги копятся и выводятся **по магазину**, а не по продавцу целиком: один
подключённый бот — один магазин со своей кассой. У продавца с тремя ботами
три отдельных накопления, и каждое ждёт своего минимума.

Доля продавца по каждому заказу пишется в `payouts`, но переводом уходит не
она сама, а `PayoutBatch` — сумма накопленных долей одного магазина. Так сделано из-за
минимальной суммы перевода в Crypto Pay: одна продажа на пару долларов её не
набирает, и transfer отбивается с AMOUNT_TOO_SMALL. Пачка создаётся только
когда накопленное уже проходит минимум (MIN_PAYOUT_USDT), поэтому заведомо
провальных переводов мы не делаем вовсе.

transfer идёт на Telegram user_id продавца (баланс внутри @CryptoBot) —
продавец должен был хотя бы раз нажать /start у @CryptoBot. Автоматики нет:
перевод запускает только сам продавец кнопкой «Вывести». Упавшая пачка
при следующем нажатии уйдёт с тем же spend_id (случайный токен из самой
пачки, не её номер), поэтому двойной выплаты не будет.
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.sql import func

from app.config import get_settings
from app.db import get_session
from app.money import fmt
from app.models import Payout, PayoutBatch, Seller, SellerBot
from app.payments.client import get_crypto_pay

logger = logging.getLogger(__name__)

UNSENT = ("pending", "failed")


def _is_too_small(error: str | None) -> bool:
    reason = (error or "").lower()
    return "amount_too_small" in reason or "min_amount" in reason


def _failure_message(amount: Decimal | float, error: str | None) -> str:
    """Понятная причина вместо универсального «нажми /start»."""
    reason = (error or "").lower()
    if "not_found" in reason or ("user" in reason and "found" in reason):
        hint = "Похоже, ты ещё не нажимал /start у @CryptoBot — сделай это, и выплата уйдёт сама."
    elif "transfer" in reason and ("disabled" in reason or "not allowed" in reason):
        hint = "Переводы отключены в настройках платформы — я уже разбираюсь."
    elif "not_enough" in reason or "insufficient" in reason:
        hint = "На стороне платформы не хватило баланса — попробуй вывести позже."
    else:
        hint = "Деньги на месте: нажми «Вывести» ещё раз, когда проблема уйдёт."
    detail = f"\n\n<code>{error}</code>" if error else ""
    return f"⚠️ Выплата {fmt(amount)} USDT пока не ушла.\n{hint}{detail}"


async def pending_total(session, bot_id: int) -> Decimal:
    """Сколько в этом магазине накоплено и ещё не выплачено."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.bot_id == bot_id, Payout.status.in_(UNSENT)
            )
        )
    ).scalar_one()
    return Decimal(total)


async def paid_total(session, bot_id: int) -> Decimal:
    """Сколько этот магазин уже получил на руки."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.bot_id == bot_id, Payout.status == "sent"
            )
        )
    ).scalar_one()
    return Decimal(total)


async def _claim_batch(session, bot_id: int, minimum: Decimal) -> PayoutBatch | None:
    """Пачка к отправке: незавершённая существующая или новая, если набралось.

    Возвращает None, если отправлять нечего — тогда доли просто копятся дальше
    и продавца мы не тревожим. Выплаты выбираются с FOR UPDATE: продавец может
    нажать «Вывести» в двух вкладках сразу, и без блокировки получилось бы два
    перевода по одним и тем же деньгам.
    """
    batch = (
        await session.execute(
            select(PayoutBatch)
            .where(PayoutBatch.bot_id == bot_id, PayoutBatch.status.in_(UNSENT))
            .order_by(PayoutBatch.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if batch is not None:
        return batch

    payouts = list(
        (
            await session.execute(
                select(Payout)
                .where(
                    Payout.bot_id == bot_id,
                    Payout.status.in_(UNSENT),
                    Payout.batch_id.is_(None),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    total = sum((Decimal(p.amount) for p in payouts), Decimal(0))
    if not payouts or total < minimum:
        return None

    batch = PayoutBatch(seller_id=payouts[0].seller_id, bot_id=bot_id, amount=total)
    session.add(batch)
    await session.flush()
    for payout in payouts:
        payout.batch_id = batch.id
    return batch


async def flush_shop_payouts(bot_id: int) -> bool:
    """Отправить накопленное по магазину. True — перевод ушёл этим вызовом."""
    crypto = get_crypto_pay()
    if crypto is None:
        return False  # нет токена (локальная разработка) — выплаты остаются pending

    minimum = Decimal(str(get_settings().min_payout_usdt))

    async with get_session() as session:
        batch = await _claim_batch(session, bot_id, minimum)
        if batch is None:
            await session.commit()
            return False
        seller = await session.get(Seller, batch.seller_id)
        shop = await session.get(SellerBot, bot_id)
        batch_id, amount = batch.id, Decimal(batch.amount)
        # идемпотентность на стороне Crypto Pay: случайный токен из самой пачки,
        # а не её порядковый id (после сброса базы id начнутся заново)
        spend_token = batch.spend_id
        seller_tg, shop_name = seller.telegram_id, shop.bot_username
        await session.commit()

    try:
        transfer = await crypto.transfer(
            user_id=seller_tg,
            asset="USDT",
            amount=float(amount),
            spend_id=spend_token,
        )
        ok, transfer_id, error = True, transfer.transfer_id, None
    except Exception as exc:
        logger.exception("Transfer не прошёл для batch=%s (seller_tg=%s)", batch_id, seller_tg)
        ok, transfer_id, error = False, None, f"{type(exc).__name__}: {exc}"[:512]

    too_small = not ok and _is_too_small(error)

    async with get_session() as session:
        batch = await session.get(PayoutBatch, batch_id)
        payouts = list(
            (await session.execute(select(Payout).where(Payout.batch_id == batch_id)))
            .scalars()
            .all()
        )
        if ok:
            batch.status, batch.transfer_id, batch.sent_at, batch.last_error = (
                "sent",
                transfer_id,
                func.now(),
                None,
            )
            for payout in payouts:
                payout.status, payout.transfer_id, payout.sent_at = "sent", transfer_id, func.now()
                payout.last_error = None
        elif too_small:
            # Минимум Crypto Pay выше нашего MIN_PAYOUT_USDT: распускаем пачку,
            # доли копятся дальше и уйдут вместе со следующими продажами.
            batch.status, batch.last_error = "too_small", error
            for payout in payouts:
                payout.batch_id, payout.last_error = None, error
            logger.warning(
                "Crypto Pay считает %s USDT слишком малой суммой — поднимите MIN_PAYOUT_USDT",
                amount,
            )
        else:
            batch.status, batch.last_error = "failed", error
            for payout in payouts:
                payout.status, payout.last_error = "failed", error
        await session.commit()

    if ok:
        await _notify_seller(
            seller_tg,
            f"💸 Выплата <b>{fmt(amount)} USDT</b> по магазину @{shop_name} "
            "отправлена в @CryptoBot.",
        )
    elif not too_small:
        await _notify_seller(seller_tg, _failure_message(amount, error))
    return ok


async def _notify_seller(seller_tg: int, text: str) -> None:
    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(seller_tg, text)
    except Exception:
        logger.exception("Не удалось уведомить продавца о выплате")
