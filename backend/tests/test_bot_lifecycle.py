from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Customer, Order, Product, SellerBot
from app.services.bot_connect import connect_seller_bot, delete_bot, disconnect_bot, enable_bot
from tests.test_bot_connect import VALID_TOKEN, make_seller, mock_get_me

patch_webhook_removal = patch(
    "app.services.bot_connect.remove_seller_webhook", new=AsyncMock()
)


async def connect(db, seller_id) -> int:
    with mock_get_me():
        result = await connect_seller_bot(seller_id, VALID_TOKEN)
    assert result.ok
    return result.bot_record.id


@pytest.mark.asyncio
async def test_disconnect_enable_cycle(db):
    seller_id = await make_seller(db)
    bot_id = await connect(db, seller_id)

    with patch_webhook_removal:
        bot = await disconnect_bot(bot_id, seller_id)
    assert bot is not None and not bot.is_active

    bot = await enable_bot(bot_id, seller_id)
    assert bot is not None and bot.is_active

    # чужой продавец управлять ботом не может
    other_id = await make_seller(db, telegram_id=999)
    with patch_webhook_removal:
        assert await disconnect_bot(bot_id, other_id) is None


@pytest.mark.asyncio
async def test_reconnect_disconnected_bot_via_token(db):
    seller_id = await make_seller(db)
    bot_id = await connect(db, seller_id)
    with patch_webhook_removal:
        await disconnect_bot(bot_id, seller_id)

    # повторный ввод токена реактивирует бота, а не даёт "already_yours"
    with mock_get_me():
        result = await connect_seller_bot(seller_id, VALID_TOKEN)
    assert result.ok
    assert result.bot_record.id == bot_id
    assert result.bot_record.is_active


@pytest.mark.asyncio
async def test_delete_bot_without_orders_removes_customers(db):
    seller_id = await make_seller(db)
    bot_id = await connect(db, seller_id)
    async with db() as session:
        session.add(Customer(telegram_id=777, seller_id=seller_id, bot_id=bot_id))
        await session.commit()

    with patch_webhook_removal:
        assert await delete_bot(bot_id, seller_id) == "deleted"

    async with db() as session:
        assert await session.get(SellerBot, bot_id) is None
        customers = (await session.execute(select(Customer))).scalars().all()
        assert customers == []


@pytest.mark.asyncio
async def test_delete_bot_with_orders_only_disconnects(db):
    seller_id = await make_seller(db)
    bot_id = await connect(db, seller_id)
    async with db() as session:
        customer = Customer(telegram_id=777, seller_id=seller_id, bot_id=bot_id)
        product = Product(
            seller_id=seller_id, bot_id=bot_id, type="physical", title="X", price=Decimal("5")
        )
        session.add_all([customer, product])
        await session.flush()
        session.add(
            Order(
                seller_id=seller_id,
                bot_id=bot_id,
                customer_id=customer.id,
                total=Decimal("5"),
            )
        )
        await session.commit()

    with patch_webhook_removal:
        assert await delete_bot(bot_id, seller_id) == "has_orders"

    async with db() as session:
        bot = await session.get(SellerBot, bot_id)
        assert bot is not None and not bot.is_active  # отключён, но не удалён
        assert (await session.execute(select(Customer))).scalars().all() != []
