"""Выплаты продавцам через Crypto Pay transfer.

transfer идёт на Telegram user_id продавца (баланс внутри @CryptoBot) — продавец
должен был хотя бы раз нажать /start у @CryptoBot. Если нет — transfer падает,
мы помечаем выплату failed и просим продавца подключиться; ретраи идемпотентны
благодаря spend_id."""

import logging

from sqlalchemy import select

from app.db import get_session
from app.models import Payout, Seller
from app.payments.client import get_crypto_pay

logger = logging.getLogger(__name__)


async def send_payout(payout_id: int) -> bool:
    crypto = get_crypto_pay()
    if crypto is None:
        return False  # нет токена (локальная разработка) — выплата остаётся pending

    async with get_session() as session:
        payout = await session.get(Payout, payout_id)
        if payout is None or payout.status == "sent":
            return payout is not None and payout.status == "sent"
        seller = await session.get(Seller, payout.seller_id)
        seller_tg = seller.telegram_id
        amount = float(payout.amount)

    try:
        transfer = await crypto.transfer(
            user_id=seller_tg,
            asset="USDT",
            amount=amount,
            spend_id=f"payout-{payout_id}",  # идемпотентность на стороне Crypto Pay
        )
        ok, transfer_id = True, transfer.transfer_id
    except Exception:
        logger.exception("Transfer не прошёл для payout=%s (seller_tg=%s)", payout_id, seller_tg)
        ok, transfer_id = False, None

    from sqlalchemy.sql import func

    async with get_session() as session:
        payout = await session.get(Payout, payout_id)
        if ok:
            payout.status = "sent"
            payout.transfer_id = transfer_id
            payout.sent_at = func.now()
        else:
            payout.status = "failed"
        await session.commit()

    if not ok:
        from app.bots.hub import hub_bot

        try:
            await hub_bot.send_message(
                seller_tg,
                f"⚠️ Не удалось отправить выплату {amount} USDT.\n"
                "Проверь, что ты нажал /start у @CryptoBot, — мы повторим "
                "выплату автоматически в течение часа.",
            )
        except Exception:
            logger.exception("Не удалось уведомить продавца о неудачной выплате")
    return ok


async def process_unsent_payouts() -> None:
    """Ежечасный ретрай pending/failed выплат («пачкой», как в брифе)."""
    async with get_session() as session:
        result = await session.execute(
            select(Payout.id).where(Payout.status.in_(("pending", "failed")))
        )
        payout_ids = [row[0] for row in result.all()]

    for payout_id in payout_ids:
        try:
            await send_payout(payout_id)
        except Exception:
            logger.exception("Ошибка при ретрае выплаты %s", payout_id)
