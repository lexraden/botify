"""Оплата Pro звёздами: подтверждение счёта и зачисление.

Счёт выставляет hub-бот (app/payments/subscription.py), поэтому и оба апдейта
приходят сюда же. Кабинет продавца открыт из этого же бота — покупка проходит
не выходя из приложения.
"""

import logging

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery

from app.config import get_settings
from app.db import get_session
from app.models import Seller
from app.payments.subscription import grant_plan, parse_payload
from app.services import seller_texts

logger = logging.getLogger(__name__)

router = Router(name="hub-subscription")


@router.pre_checkout_query()
async def confirm(query: PreCheckoutQuery) -> None:
    """Ответить Telegram обязательно и в течение 10 секунд, иначе он сам
    отменит платёж. Проверяем только то, что счёт наш и разбирается."""
    ok = parse_payload(query.invoice_payload) is not None
    try:
        await query.answer(ok=ok, error_message=None if ok else "Счёт не распознан")
    except Exception:
        logger.exception("Не удалось ответить на pre_checkout_query")


@router.message(F.successful_payment)
async def paid(message: Message) -> None:
    payment = message.successful_payment
    parsed = parse_payload(payment.invoice_payload)
    if parsed is None:
        logger.error("successful_payment с чужим payload: %s", payment.invoice_payload)
        return
    seller_id, plan = parsed

    granted = await grant_plan(
        seller_id,
        plan,
        method="stars",
        telegram_charge_id=payment.telegram_payment_charge_id,
        amount_stars=payment.total_amount,
    )
    if not granted:
        return  # повторная доставка — второе сообщение продавцу не нужно

    # язык — из строки продавца, как во всех остальных пушах кабинета
    async with get_session() as session:
        seller = await session.get(Seller, seller_id)
        locale = seller_texts.seller_locale(seller)
    await message.answer(
        seller_texts.text(
            locale, "pro.paid", plan=plan.capitalize(), days=get_settings().pro_period_days
        )
    )
