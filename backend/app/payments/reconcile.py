"""Сверка оплаченных счетов с заказами: последняя сетка под платежами.

Вебхук — основной путь, но не единственно возможный. Он может не дойти вовсе
(в настройках приложения Crypto Pay не прописан URL, деплой лежал минуту) или
упасть на нашей стороне столько раз, что провайдер перестанет повторять. Тогда
деньги приняты, а заказ остался `pending_payment` — и без сверки узнать об этом
было нечем: покупатель считает, что заплатил, продавец не видит заказа.

Сверка спрашивает у Crypto Pay статус счетов по заказам, которые всё ещё ждут
оплату, и до-обрабатывает те, что на самом деле оплачены. Обработка та же самая
(`handle_invoice_paid`) и идемпотентная, поэтому гонка с опоздавшим вебхуком
безопасна: кто первый, того и заказ, второй увидит статус не `pending_payment`
и ничего не сделает.

Опирается на инвариант «у заказа не больше одного оплачиваемого счёта»: отмена
и выдача новой ссылки снимают предыдущий (`payments/service.py:discard_invoice`),
поэтому `orders.invoice_id` — актуальный счёт, а не один из нескольких живых.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.models import Order
from app.payments.client import get_crypto_pay

logger = logging.getLogger(__name__)

# Сколько счетов спрашивать за один вызов get_invoices. Ограничение сверху —
# длина URL: invoice_ids уходят списком в query.
BATCH = 100


async def reconcile_paid_invoices() -> int:
    """До-обработать оплаченные счета, о которых не сообщил вебхук.

    Возвращает число заказов, которые сверка перевела в оплаченные.
    """
    from app.payments.service import handle_invoice_paid

    crypto = get_crypto_pay()
    if crypto is None:
        return 0

    settings = get_settings()
    # Окно: счёт живёт час, плюс запас на задержки. Смотреть глубже незачем —
    # более старые счета давно протухли и оплачены быть не могли.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.reconcile_window_hours)

    async with get_session() as session:
        waiting = list(
            (
                await session.execute(
                    select(Order.invoice_id)
                    .where(
                        Order.status == "pending_payment",
                        Order.invoice_id.is_not(None),
                        Order.created_at >= cutoff,
                    )
                    .order_by(Order.id.desc())
                    .limit(BATCH)
                )
            )
            .scalars()
            .all()
        )
    if not waiting:
        return 0

    try:
        invoices = await crypto.get_invoices(invoice_ids=waiting)
    except Exception:
        logger.exception("Сверка: не удалось получить счета из Crypto Pay")
        return 0

    # при одном id библиотека отдаёт объект, при нескольких — список
    if invoices is None:
        return 0
    if not isinstance(invoices, list):
        invoices = [invoices]

    recovered = 0
    for invoice in invoices:
        if getattr(invoice, "status", None) != "paid":
            continue
        fee = getattr(invoice, "fee_amount", None)
        if fee is not None and getattr(invoice, "fee_asset", None) not in (None, "USDT"):
            fee = None  # комиссия в другой валюте — посчитаем по ставке
        try:
            done = await handle_invoice_paid(
                invoice_id=invoice.invoice_id,
                payload=getattr(invoice, "payload", None),
                fee_amount=Decimal(str(fee)) if fee is not None else None,
            )
        except Exception:
            logger.exception("Сверка: обработка счёта %s не удалась", invoice.invoice_id)
            continue
        if done:
            recovered += 1
            logger.warning(
                "Сверка добрала оплату по счёту %s — вебхук по нему не дошёл",
                invoice.invoice_id,
            )
    return recovered
