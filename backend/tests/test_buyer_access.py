"""Доступ покупателя к своему: отключённый магазин и выключенная витрина.

Обе ситуации создаёт продавец одним тапом, а расплачивается за них покупатель,
который уже заплатил. Витрину закрыть можно — историю покупок и связь с
продавцом нельзя.
"""

import pytest
from sqlalchemy import select

from app.models import Order, SellerBot
from tests.test_api import buyer_headers, client, seller_headers, setup_shop

DELIVERY = {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}


async def _order_in_shop(c, bot_id: int) -> int:
    r = await c.post(
        f"/api/seller/bots/{bot_id}/products",
        headers=seller_headers(),
        json={"type": "physical", "title": "Кружка", "price": "5"},
    )
    pid = r.json()["id"]
    r = await c.post(
        f"/api/store/{bot_id}/orders",
        headers=buyer_headers(),
        json={"delivery": DELIVERY, "items": [{"product_id": pid, "qty": 1}]},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_disabled_shop_keeps_buyer_orders_reachable(db):
    """Продавец нажал «Отключить». Витрина закрыта — это правильно. Но заказ
    покупателя уже оплачен, и отбирать вместе с витриной его историю нельзя."""
    bot_id = await setup_shop(db)
    async with client() as c:
        order_id = await _order_in_shop(c, bot_id)

        async with db() as session:
            shop = await session.get(SellerBot, bot_id)
            shop.is_active = False
            await session.commit()

        # витрина закрыта
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert r.status_code == 404

        # свои покупки — на месте
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        assert r.status_code == 200, r.text
        assert [o["id"] for o in r.json()] == [order_id]

        # и отменить неоплаченный заказ по-прежнему можно
        r = await c.post(f"/api/store/{bot_id}/orders/{order_id}/cancel", headers=buyer_headers())
        assert r.status_code == 200, r.text

    async with db() as session:
        assert (await session.get(Order, order_id)).status == "cancelled"


@pytest.mark.asyncio
async def test_disabled_shop_does_not_accept_new_orders(db):
    """Закрыт — значит закрыт: покупать в отключённом магазине нельзя."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "5"},
        )
        pid = r.json()["id"]

        async with db() as session:
            shop = await session.get(SellerBot, bot_id)
            shop.is_active = False
            await session.commit()

        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"delivery": DELIVERY, "items": [{"product_id": pid, "qty": 1}]},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_hidden_catalog_still_lets_buyers_reach_their_orders(db):
    """Продавец выключил кнопку каталога. У покупателя с заказом это забирало
    единственный вход в приложение — вместе с историей и чатом."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.handlers.seller.start import MY_ORDERS_BUTTON, catalog_keyboard
    from app.models import Customer

    bot_id = await setup_shop(db)
    async with client() as c:
        await _order_in_shop(c, bot_id)

    async with db() as session:
        shop = await session.get(SellerBot, bot_id)
        shop.show_catalog_button = False
        await session.commit()
        buyer = (await session.execute(select(Customer))).scalars().first()
        stranger = Customer(telegram_id=999, seller_id=shop.seller_id, bot_id=bot_id)
        session.add(stranger)
        await session.commit()
        shop = await session.get(SellerBot, bot_id)
        buyer_id, stranger_id = buyer.id, stranger.id

    # без публичного адреса Mini App кнопок нет вовсе — задаём его для проверки
    fake_settings = SimpleNamespace(effective_webapp_url="https://shop.example")
    with patch("app.handlers.seller.start.get_settings", return_value=fake_settings):
        kb = await catalog_keyboard(shop, SimpleNamespace(id=buyer_id))
        assert kb is not None
        assert kb.inline_keyboard[0][0].text == MY_ORDERS_BUTTON

        # тем, кто ничего не покупал, каталог не навязываем — кнопки нет
        assert await catalog_keyboard(shop, SimpleNamespace(id=stranger_id)) is None


@pytest.mark.asyncio
async def test_shipped_is_not_delivered_until_buyer_says_so(db):
    """Отправка и получение — разные события. Раньше «Доставлен» ставился в
    момент отправки, и 72-часовое окно чата тикало, пока посылка ещё едет."""
    from unittest.mock import AsyncMock, patch

    from app.services.chat import chat_is_open
    from tests.test_fulfillment import paid_physical_order

    bot_id, order_id = await paid_physical_order(db)
    async with client() as c:
        with patch("app.payments.service._notify", new=AsyncMock()):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"value": "RA1"},
            )
        assert r.json()["status"] == "fulfilled"

        async with db() as session:
            order = await session.get(Order, order_id)
            assert order.delivered_at is None
            # окно чата ещё не начиналось — писать продавцу можно
            assert chat_is_open(order) is True

        r = await c.post(f"/api/store/{bot_id}/orders/{order_id}/received", headers=buyer_headers())
        assert r.status_code == 200, r.text

    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "delivered"
        assert order.delivered_at is not None


@pytest.mark.asyncio
async def test_forgotten_confirmation_closes_itself(db):
    """Часть людей кнопку просто не нажмёт: без страховки заказ навис бы
    навсегда — окно чата не начинается, оценить покупку нельзя."""
    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock, patch

    from app.services.order_health import auto_confirm_delivery
    from tests.test_fulfillment import paid_physical_order

    bot_id, order_id = await paid_physical_order(db)
    async with client() as c:
        with patch("app.payments.service._notify", new=AsyncMock()):
            await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"value": "RA1"},
            )

    assert await auto_confirm_delivery() == 0  # свежий заказ не трогаем

    async with db() as session:
        order = await session.get(Order, order_id)
        order.paid_at = datetime.now(timezone.utc) - timedelta(days=30)
        await session.commit()

    assert await auto_confirm_delivery() == 1
    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "delivered"
        assert order.delivered_at is not None
