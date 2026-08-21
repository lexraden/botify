"""Выплаты продавцам через Crypto Pay transfer.

Доля продавца по каждому заказу пишется в `payouts`, но переводом уходит не
она сама, а `PayoutBatch` — сумма всех накопленных долей. Так сделано из-за
минимальной суммы перевода в Crypto Pay: одна продажа на пару долларов её не
набирает, и transfer отбивается с AMOUNT_TOO_SMALL. Пачка создаётся только
когда накопленное уже проходит минимум (MIN_PAYOUT_USDT), поэтому заведомо
провальных переводов мы не делаем вовсе.

transfer идёт на Telegram user_id продавца (баланс внутри @CryptoBot) —
продавец должен был хотя бы раз нажать /start у @CryptoBot. Если нет —
transfer падает, пачка помечается failed и ретраится с тем же spend_id,
поэтому двойной выплаты не будет.
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.sql import func

from app.config import get_settings
from app.db import get_session
from app.models import Payout, PayoutBatch, Seller
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
        hint = "На стороне платформы не хватило баланса — выплата уйдёт при следующем ретрае."
    else:
        hint = "Мы повторим выплату автоматически в течение часа."
    detail = f"\n\n<code>{error}</code>" if error else ""
    return f"⚠️ Выплата {amount} USDT пока не ушла.\n{hint}{detail}"


async def pending_payout_total(seller_id: int) -> Decimal:
    """Сколько у продавца накоплено и ещё не выплачено."""
    async with get_session() as session:
        return await pending_total(session, seller_id)


async def pending_total(session, seller_id: int) -> Decimal:
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.seller_id == seller_id, Payout.status.in_(UNSENT)
            )
        )
    ).scalar_one()
    return Decimal(total)


async def _claim_batch(session, seller_id: int, minimum: Decimal) -> PayoutBatch | None:
    """Пачка к отправке: незавершённая существующая или новая, если набралось.

    Возвращает None, если отправлять нечего — тогда доли просто копятся дальше
    и продавца мы не тревожим.
    """
    batch = (
        await session.execute(
            select(PayoutBatch)
            .where(PayoutBatch.seller_id == seller_id, PayoutBatch.status.in_(UNSENT))
            .order_by(PayoutBatch.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if batch is not None:
        return batch

    payouts = list(
        (
            await session.execute(
                select(Payout).where(
                    Payout.seller_id == seller_id,
                    Payout.status.in_(UNSENT),
                    Payout.batch_id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    total = sum((Decimal(p.amount) for p in payouts), Decimal(0))
    if not payouts or total < minimum:
        return None

    batch = PayoutBatch(seller_id=seller_id, amount=total)
    session.add(batch)
    await session.flush()
    for payout in payouts:
        payout.batch_id = batch.id
    return batch


async def flush_seller_payouts(seller_id: int) -> bool:
    """Отправить накопленное продавцу. True — перевод ушёл этим вызовом."""
    crypto = get_crypto_pay()
    if crypto is None:
        return False  # нет токена (локальная разработка) — выплаты остаются pending

    minimum = Decimal(str(get_settings().min_payout_usdt))

    async with get_session() as session:
        batch = await _claim_batch(session, seller_id, minimum)
        if batch is None:
            await session.commit()
            return False
        seller = await session.get(Seller, seller_id)
        batch_id, amount, seller_tg = batch.id, Decimal(batch.amount), seller.telegram_id
        await session.commit()

    try:
        transfer = await crypto.transfer(
            user_id=seller_tg,
            asset="USDT",
            amount=float(amount),
            spend_id=f"batch-{batch_id}",  # идемпотентность на стороне Crypto Pay
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
        await _notify_seller(seller_tg, f"💸 Выплата <b>{amount} USDT</b> отправлена в @CryptoBot.")
    elif not too_small:
        await _notify_seller(seller_tg, _failure_message(amount, error))
    return ok


async def _notify_seller(seller_tg: int, text: str) -> None:
    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(seller_tg, text)
    except Exception:
        logger.exception("Не удалось уведомить продавца о выплате")


async def send_payout(payout_id: int) -> bool:
    """Попытка выплаты после конкретного заказа: уйдёт всё накопленное сразу."""
    async with get_session() as session:
        payout = await session.get(Payout, payout_id)
        if payout is None:
            return False
        if payout.status == "sent":
            return True
        seller_id = payout.seller_id
    return await flush_seller_payouts(seller_id)


async def process_unsent_payouts() -> None:
    """Ежечасный ретрай: по одному переводу на продавца, а не на заказ."""
    async with get_session() as session:
        sellers = [
            row[0]
            for row in (
                await session.execute(
                    select(Payout.seller_id).where(Payout.status.in_(UNSENT)).distinct()
                )
            ).all()
        ]

    for seller_id in sellers:
        try:
            await flush_seller_payouts(seller_id)
        except Exception:
            logger.exception("Ошибка при ретрае выплат продавца %s", seller_id)
