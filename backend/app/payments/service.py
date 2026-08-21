"""Платёжный флоу: инвойс на заказ -> invoice_paid -> уведомления, выдача digital,
запись Payout (сам transfer продавцу — этап 6)."""

import logging
from decimal import Decimal

from sqlalchemy import select

from app.bots.runner import make_seller_bot
from app.config import get_settings
from app.db import get_session
from app.money import fmt
from app.models import Customer, Order, OrderItem, Payout, Product, Seller
from app.payments.client import get_crypto_pay
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)


async def create_invoice_for_order(order_id: int, total: Decimal) -> str | None:
    """Создаёт инвойс Crypto Pay. Возвращает ссылку на оплату (или None без токена)."""
    crypto = get_crypto_pay()
    if crypto is None:
        return None
    invoice = await crypto.create_invoice(
        asset="USDT",
        amount=float(total),
        description=f"Заказ #{order_id}",
        payload=f"order:{order_id}",
        allow_comments=False,
        allow_anonymous=False,
        expires_in=3600,
    )
    async with get_session() as session:
        order = await session.get(Order, order_id)
        if order is not None:
            order.invoice_id = invoice.invoice_id
            await session.commit()
    return invoice.bot_invoice_url


def _provider_fee(total: Decimal, fee_amount: Decimal | None) -> Decimal:
    """Сколько Crypto Pay удержал с этого платежа.

    На долю продавца не влияет — это расход платформы из её же комиссии.
    Пишем в БД, чтобы маржа была видна: наша комиссия минус эта сумма.
    Точное значение приходит в вебхуке (fee_amount), иначе — по ставке.
    """
    if fee_amount is not None and fee_amount >= 0:
        return Decimal(fee_amount).quantize(Decimal("0.000001"))
    rate = Decimal(str(get_settings().crypto_pay_fee_pct))
    return (total * rate / 100).quantize(Decimal("0.000001"))


async def handle_invoice_paid(
    invoice_id: int, payload: str | None, fee_amount: Decimal | None = None
) -> bool:
    """Обработка вебхука invoice_paid. Идемпотентна: повторный вызов — no-op.
    Возвращает True, если заказ был переведён в оплаченные этим вызовом."""
    from sqlalchemy.sql import func

    async with get_session() as session:
        order = (
            await session.execute(select(Order).where(Order.invoice_id == invoice_id))
        ).scalar_one_or_none()
        if order is None and payload and payload.startswith("order:"):
            order = await session.get(Order, int(payload.split(":", 1)[1]))

        if order is None:
            logger.warning("invoice_paid для неизвестного invoice_id=%s", invoice_id)
            return False
        if order.status != "pending_payment":
            return False  # уже обработан (ретрай вебхука)

        order.status = "paid"
        order.paid_at = func.now()

        seller = await session.get(Seller, order.seller_id)
        customer = await session.get(Customer, order.customer_id)

        # С продавца берём только нашу комиссию. Комиссию Crypto Pay платформа
        # платит из неё же, поэтому доля продавца от неё не зависит; сама
        # комиссия сервиса пишется в provider_fee, чтобы видеть реальную маржу.
        commission = (order.total * seller.commission_pct / 100).quantize(Decimal("0.000001"))
        provider_fee = _provider_fee(order.total, fee_amount)
        payout = Payout(
            order_id=order.id,
            seller_id=seller.id,
            bot_id=order.bot_id,
            amount=order.total - commission,
            commission=commission,
            provider_fee=provider_fee,
        )
        session.add(payout)
        await session.flush()
        payout_id = payout.id

        items = (
            await session.execute(
                select(OrderItem, Product)
                .join(Product, Product.id == OrderItem.product_id)
                .where(OrderItem.order_id == order.id)
            )
        ).all()

        # Digital/услуги с настроенной выдачей доставляются сразу
        digital_lines = [
            f"• {product.title}: {product.digital_content['url']}"
            for _, product in items
            if product.type in ("digital", "service")
            and product.digital_content
            and product.digital_content.get("url")
        ]
        all_digital = all(product.type in ("digital", "service") for _, product in items)
        if digital_lines and all_digital:
            order.status = "delivered"

        order_summary = "\n".join(
            f"• {product.title} × {item.qty}" for item, product in items
        )
        await session.commit()

        order_id, order_total = order.id, order.total
        customer_tg = customer.telegram_id
        seller_tg = seller.telegram_id

        # Токен бота покупателя — для уведомления в ЛС
        await session.refresh(customer, ["bot"])
        seller_bot_token = decrypt_bot_token(customer.bot.bot_token_encrypted)

    await _notify(
        seller_bot_token,
        customer_tg,
        f"✅ Заказ #{order_id} оплачен!\n\n{order_summary}\n"
        + (
            "\n📬 Твои материалы:\n" + "\n".join(digital_lines)
            if digital_lines
            else "\nПродавец готовит заказ — детали доставки придут сюда."
        ),
    )

    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(
            seller_tg,
            f"💰 Твой товар купили! Заказ #{order_id} на {fmt(order_total)} USDT оплачен.\n"
            + (
                "Digital-контент выдан автоматически."
                if digital_lines and all_digital
                else "Открой кабинет, чтобы отправить заказ и прикрепить трек/ссылку."
            ),
        )
    except Exception:
        logger.exception("Не удалось уведомить продавца о заказе %s", order_id)

    # Digital-заказ закрыт — сразу пробуем выплату; физические ждут fulfillment
    if digital_lines and all_digital:
        from app.payments.payouts import send_payout

        try:
            await send_payout(payout_id)
        except Exception:
            logger.exception("Выплата по заказу %s не отправлена (будет ретрай)", order_id)

    return True


async def _notify(bot_token: str, chat_id: int, text: str) -> None:
    bot = make_seller_bot(bot_token)
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("Не удалось отправить уведомление chat_id=%s", chat_id)
    finally:
        await bot.session.close()
