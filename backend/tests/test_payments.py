from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Customer, Order, OrderItem, Payout, Product, Seller, SellerBot
from app.payments.service import handle_invoice_paid
from app.security import encrypt_bot_token


async def make_order(
    db,
    product_type="digital",
    digital_url="https://guide.example/x",
    total=Decimal("100"),
    invoice_id=555001,
):
    """Заказ в ожидании оплаты. Повторный вызов вешает заказ на того же продавца."""
    async with db() as session:
        seller = (await session.execute(select(Seller).where(Seller.telegram_id == 111))).scalar_one_or_none()
        if seller is None:
            seller = Seller(telegram_id=111, cryptobot_connected=True)
            session.add(seller)
            await session.flush()
            bot = SellerBot(
                seller_id=seller.id,
                bot_token_encrypted=encrypt_bot_token("111:token-for-tests-aaaaaaaaaaaaaaaaaaaaaa"),
                bot_username="shop_bot",
                telegram_bot_id=42,
            )
            session.add(bot)
            await session.flush()
            session.add(Customer(telegram_id=777, seller_id=seller.id, bot_id=bot.id))
            await session.flush()
        bot = (await session.execute(select(SellerBot).where(SellerBot.seller_id == seller.id))).scalars().first()
        customer = (await session.execute(select(Customer).where(Customer.bot_id == bot.id))).scalars().first()
        product = Product(
            seller_id=seller.id,
            bot_id=bot.id,
            type=product_type,
            title="Гайд",
            price=total,
            digital_content={"url": digital_url} if digital_url else None,
        )
        session.add(product)
        await session.flush()
        order = Order(
            seller_id=seller.id,
            bot_id=bot.id,
            customer_id=customer.id,
            total=total,
            invoice_id=invoice_id,
        )
        session.add(order)
        await session.flush()
        session.add(OrderItem(order_id=order.id, product_id=product.id, qty=1, price=product.price))
        await session.commit()
        return order.id


def patched_notifications():
    return (
        patch("app.payments.service._notify", new=AsyncMock()),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_invoice_paid_delivers_digital_and_creates_payout(db):
    order_id = await make_order(db)
    p1, p2 = patched_notifications()
    with p1 as notify_mock, p2 as hub_mock:
        assert await handle_invoice_paid(555001, None) is True

    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "delivered"  # digital выдан сразу
        assert order.paid_at is not None
        payout = (await session.execute(select(Payout))).scalar_one()
        # с продавца только наши 5%; комиссию сервиса платим из них
        assert payout.commission == Decimal("5")
        assert payout.provider_fee == Decimal("3")
        assert payout.amount == Decimal("95")
        assert payout.status == "pending"

    # покупатель получил ссылку, продавец — уведомление
    buyer_text = notify_mock.call_args.args[2]
    assert "https://guide.example/x" in buyer_text
    assert hub_mock.await_count == 1


@pytest.mark.asyncio
async def test_invoice_paid_is_idempotent(db):
    await make_order(db)
    p1, p2 = patched_notifications()
    with p1, p2:
        assert await handle_invoice_paid(555001, None) is True
        assert await handle_invoice_paid(555001, None) is False  # ретрай вебхука

    async with db() as session:
        payouts = (await session.execute(select(Payout))).scalars().all()
        assert len(payouts) == 1


@pytest.mark.asyncio
async def test_physical_order_waits_for_fulfillment(db):
    order_id = await make_order(db, product_type="physical", digital_url=None)
    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)

    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "paid"  # ждёт действий продавца


@pytest.mark.asyncio
async def test_unknown_invoice_ignored(db):
    p1, p2 = patched_notifications()
    with p1, p2:
        assert await handle_invoice_paid(999999, None) is False
