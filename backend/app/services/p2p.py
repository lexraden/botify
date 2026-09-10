"""Оплата переводом на реквизиты продавца: способы приёма и подтверждение.

Схема расчётов принципиально отличается от Crypto Pay: платформа денег не
видит и не держит. Отсюда всё остальное —

- подтвердить оплату может только продавец (`confirm_p2p_payment` в
  app/payments/service.py): ни вебхука, ни сверки здесь нет физически;
- выплаты по такому заказу не заводятся, комиссия не берётся;
- заказ, по которому покупатель нажал «я оплатил», не отменяется по таймеру —
  ждёт продавца сколько угодно, с напоминаниями (`remind_unconfirmed`).

Способ приёма — функция тарифа Pro (`plans.p2p_payments`). Проверка тарифа
живёт в API, а не здесь: этот модуль отвечает за данные, а не за доступ.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.sql import func

from app.config import get_settings
from app.db import get_session
from app.models import Order, Seller, SellerBot
from app.models.payment_methods import KINDS, ShopPaymentMethod
from app.money import fmt
from app.services.seller_texts import seller_locale, text

logger = logging.getLogger(__name__)

# Сколько способов приёма можно завести на магазин: список выбора на чекауте
# должен читаться, а не листаться
MAX_METHODS = 8


class MethodError(ValueError):
    """Реквизиты не приняты — текст ошибки уходит продавцу как есть."""


def clean_method_fields(
    kind: str, label: str, account: str, holder: str | None, note: str | None
) -> tuple[str, str, str, str | None, str | None]:
    """Нормализовать и проверить поля способа приёма.

    Номер не валидируется по маске намеренно: карта, телефон СБП и адрес
    кошелька выглядят по-разному, а перевод всё равно идёт мимо платформы —
    единственный, кто может заметить опечатку, это сам продавец.
    """
    kind = (kind or "").strip()
    if kind not in KINDS:
        raise MethodError("unknown kind")
    label = (label or "").strip()
    account = (account or "").strip()
    if not label or not account:
        raise MethodError("label and account are required")
    holder = (holder or "").strip() or None
    note = (note or "").strip() or None
    return kind, label[:64], account[:128], holder[:64] if holder else None, note[:200] if note else None


async def list_methods(session, bot_id: int, *, active_only: bool = False):
    stmt = select(ShopPaymentMethod).where(ShopPaymentMethod.bot_id == bot_id)
    if active_only:
        stmt = stmt.where(ShopPaymentMethod.is_active.is_(True))
    return list((await session.execute(stmt.order_by(ShopPaymentMethod.id))).scalars().all())


async def claim_paid(session, order: Order) -> bool:
    """Покупатель отметил, что перевёл деньги. Повторное нажатие — no-op.

    Отметка снимает заказ с таймера автоотмены (order_health) и уходит
    напоминанием продавцу.
    """
    if order.payment_method != "p2p" or order.status != "pending_payment":
        return False
    if order.paid_claimed_at is not None:
        return False
    order.paid_claimed_at = func.now()
    return True


async def reject_paid(session, order: Order) -> bool:
    """Продавец говорит, что перевода не было: отметка снимается, заказ снова
    ждёт оплату и снова может истечь по таймеру."""
    if order.payment_method != "p2p" or order.status != "pending_payment":
        return False
    if order.paid_claimed_at is None:
        return False
    order.paid_claimed_at = None
    order.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=get_settings().p2p_order_ttl_minutes
    )
    return True


async def remind_unconfirmed() -> int:
    """Напомнить продавцам про переводы, которые ждут подтверждения.

    Автоподтверждения нет и не будет: платформа перевод не видела, а скрин
    подделывается за минуту (решение владельца от 2026-09-10). Поэтому
    единственный рычаг — напоминание, и оно повторяется, пока продавец не
    ответит: заказ иначе висит вечно.
    """
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.p2p_confirm_reminder_hours)

    async with get_session() as session:
        waiting = list(
            (
                await session.execute(
                    select(Order).where(
                        Order.status == "pending_payment",
                        Order.payment_method == "p2p",
                        Order.paid_claimed_at.is_not(None),
                        Order.paid_claimed_at < cutoff,
                        # reminded_at здесь же, что и у зависших оплаченных:
                        # у p2p-заказа до оплаты она свободна
                        Order.reminded_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not waiting:
            return 0

        messages: list[tuple[int, str]] = []
        for order in waiting:
            seller = await session.get(Seller, order.seller_id)
            shop = await session.get(SellerBot, order.bot_id)
            if seller is None:
                continue
            locale = seller_locale(seller)
            messages.append(
                (
                    seller.telegram_id,
                    text(
                        locale,
                        "push.p2p_waiting",
                        id=order.id,
                        amount=fmt(order.total),
                        currency=order.currency,
                        shop=shop.bot_username if shop else "",
                    ),
                )
            )
            order.reminded_at = func.now()
        await session.commit()

    from app.bots.hub import hub_bot

    for seller_tg, body in messages:
        try:
            await hub_bot.send_message(seller_tg, body)
        except Exception:
            logger.exception("Не удалось напомнить продавцу о неподтверждённом переводе")
    logger.info("Напоминаний о неподтверждённых переводах: %d", len(messages))
    return len(messages)
