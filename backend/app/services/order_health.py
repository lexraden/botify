"""Заказы, застрявшие между сторонами: не отправлен продавцом и не подтверждён
покупателем.

Отдельного признака «ручная доставка» в схеме нет и не нужно: цифровые заказы
переходят в `delivered` прямо в момент оплаты (app/payments/service.py), так
что заказ, зависший в статусе `paid`, — это ровно тот случай, когда покупатель
заплатил и ждёт действий продавца.

Пока напоминаний не было, это был тупик: покупателю написано «продавец готовит
заказ», окно чата считается от `delivered_at` и потому не закрывается вовсе, а
продавцу никто не сообщает, что деньги уже пришли, а посылка не поехала.

Напоминание уходит один раз на заказ (`orders.reminded_at`) и одним сообщением
на продавца, даже если зависших заказов несколько: десять пушей подряд читаются
как спам и работают хуже одного списка. Авто-отмена с возвратом денег сюда не
входит — рефанд через Crypto Pay требует отдельной проработки.

Вторая половина — обратная: заказ отправлен, но покупатель не нажал «Получил».
Тогда его закрывает `auto_confirm_delivery`, иначе окно чата не начинается и
оценить покупку нельзя.
"""

import html
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.sql import func

from app.config import get_settings
from app.db import get_session
from app.models import Order, Seller, SellerBot
from app.money import fmt

logger = logging.getLogger(__name__)

# Сколько заказов перечислять поимённо, прежде чем свернуть в «и ещё N»
MAX_LISTED = 5


async def expire_unpaid_orders() -> int:
    """Отменить заказы, не оплаченные за отведённое время (orders.expires_at).

    Заказ живёт столько же, сколько его счёт в Crypto Pay: без таймера брошенная
    корзина навсегда оставалась бы в «Моих покупках» и держала бы витрину в
    невыплаченных. Отмена здесь та же, что и при отмене покупателем, — счёт
    снимается (`discard_invoice`), чтобы по ссылке из @CryptoBot нельзя было
    заплатить за отменённый заказ.

    Возвращает число отменённых заказов.
    """
    from app.payments.service import discard_invoice

    async with get_session() as session:
        stale = list(
            (
                await session.execute(
                    select(Order)
                    .where(
                        Order.status == "pending_payment",
                        Order.expires_at.is_not(None),
                        Order.expires_at < func.now(),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if not stale:
            return 0
        for order in stale:
            order.status = "cancelled"
        await session.commit()

    # после коммита: сетевой вызов, его неудача не откатывает отмену
    for order in stale:
        await discard_invoice(order.invoice_id)
    logger.info("Неоплаченных заказов отменено по таймеру: %d", len(stale))
    return len(stale)


async def auto_confirm_delivery() -> int:
    """Отметить полученными заказы, отправленные давно и без подтверждения.

    «Доставлен» ставит покупатель кнопкой «Получил», но часть людей её просто
    не нажмёт. Без страховки такой заказ навис бы навсегда: окно чата не
    начинается, оценить покупку нельзя, статус вечно «Отправлен».

    Срок берётся с большим запасом на долгую доставку (`auto_deliver_days`).
    Возвращает число закрытых заказов.
    """
    days = get_settings().auto_deliver_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_session() as session:
        result = await session.execute(
            update(Order)
            .where(
                Order.status == "fulfilled",
                Order.paid_at.is_not(None),
                Order.paid_at < cutoff,
            )
            .values(status="delivered", delivered_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await session.commit()
    if result.rowcount:
        logger.info(
            "Заказов отмечено полученными автоматически (спустя %s дней): %d",
            days,
            result.rowcount,
        )
    return result.rowcount


async def remind_stuck_orders() -> int:
    """Напоминает продавцам о неотправленных оплаченных заказах.

    Возвращает число заказов, попавших в напоминания на этом проходе.
    """
    hours = get_settings().stuck_order_hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with get_session() as session:
        stuck = list(
            (
                await session.execute(
                    select(Order)
                    .where(
                        Order.status == "paid",
                        Order.paid_at.is_not(None),
                        Order.paid_at < cutoff,
                        Order.reminded_at.is_(None),
                    )
                    .order_by(Order.id)
                )
            )
            .scalars()
            .all()
        )
        if not stuck:
            return 0

        # группируем по продавцу: одно сообщение вместо пачки пушей
        by_seller: dict[int, list[Order]] = {}
        for order in stuck:
            by_seller.setdefault(order.seller_id, []).append(order)

        shop_names: dict[int, str] = {}
        for bot_id in {o.bot_id for o in stuck}:
            shop = await session.get(SellerBot, bot_id)
            shop_names[bot_id] = shop.bot_username if shop else "магазин"

        messages: list[tuple[int, str]] = []
        for seller_id, orders in by_seller.items():
            seller = await session.get(Seller, seller_id)
            if seller is None:
                continue
            messages.append((seller.telegram_id, _reminder_text(orders, shop_names, hours)))

        # отметку ставим до отправки: упавший пуш не должен превратиться
        # в бесконечное напоминание на каждом тике
        for order in stuck:
            order.reminded_at = func.now()
        await session.commit()

    for seller_tg, text in messages:
        await _notify(seller_tg, text)
    logger.info("Напоминаний о зависших заказах: %d заказов", len(stuck))
    return len(stuck)


def _reminder_text(orders: list[Order], shop_names: dict[int, str], hours: float) -> str:
    listed = orders[:MAX_LISTED]
    lines = [
        f"• Заказ #{o.id} на {fmt(o.total)} {o.currency} "
        f"(@{html.escape(shop_names.get(o.bot_id, 'магазин'))})"
        for o in listed
    ]
    if len(orders) > MAX_LISTED:
        lines.append(f"• …и ещё {len(orders) - MAX_LISTED}")

    head = (
        f"📦 Заказ оплачен больше {int(hours)} ч назад, но ещё не отправлен:"
        if len(orders) == 1
        else f"📦 Заказы оплачены больше {int(hours)} ч назад, но ещё не отправлены:"
    )
    return (
        f"{head}\n\n"
        + "\n".join(lines)
        + "\n\nПокупатель уже заплатил и ждёт. Открой кабинет и отправь — "
        "или напиши ему в чат заказа, если нужна пауза."
    )


async def _notify(seller_tg: int, text: str) -> None:
    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(seller_tg, text)
    except Exception:
        logger.exception("Не удалось напомнить продавцу о зависших заказах")
