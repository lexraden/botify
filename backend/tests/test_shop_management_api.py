"""API управления магазином из приложения: disable/enable/delete,
уведомления в hub-бот и кнопка «Открыть магазин» в подтверждении подключения."""

import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.bots.hub import hub_bot
from app.models import Customer, Order, SellerBot
from tests.test_api import client, init_data_for, seller_headers, setup_shop
from tests.test_bot_connect import VALID_TOKEN, make_seller, mock_get_me


def mocked_notify():
    return patch.object(hub_bot, "send_message", new=AsyncMock())


async def seed_order(db, bot_id: int) -> None:
    """Любой заказ у покупателей делает удаление магазина невозможным."""
    async with db() as session:
        bot = await session.get(SellerBot, bot_id)
        customer = Customer(seller_id=bot.seller_id, bot_id=bot_id, telegram_id=777)
        session.add(customer)
        await session.flush()
        session.add(
            Order(
                seller_id=bot.seller_id,
                bot_id=bot_id,
                customer_id=customer.id,
                total=Decimal("5"),
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_disable_enable_roundtrip(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        with mocked_notify() as notify:
            r = await c.post(f"/api/seller/bots/{bot_id}/disable", headers=seller_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        notify.assert_awaited_once()  # действие продублировано в hub-бот

        with mocked_notify() as notify:
            r = await c.post(f"/api/seller/bots/{bot_id}/enable", headers=seller_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is True
        notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_without_orders(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        with mocked_notify():
            r = await c.delete(f"/api/seller/bots/{bot_id}", headers=seller_headers())
        assert r.status_code == 200
        assert r.json() == {"status": "deleted"}
        # магазина больше нет — все его ресурсы отдают 404
        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_with_orders_only_disconnects(db):
    bot_id = await setup_shop(db)
    await seed_order(db, bot_id)
    async with client() as c:
        with mocked_notify():
            r = await c.delete(f"/api/seller/bots/{bot_id}", headers=seller_headers())
        assert r.status_code == 200
        assert r.json() == {"status": "has_orders"}
        # история продаж неприкосновенна: бот остался, но отключён
        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_other_seller_cannot_manage_shop(db):
    bot_id = await setup_shop(db)
    init_for = lambda: {  # noqa: E731
        "X-Init-Data": init_data_for(
            {"id": 222, "first_name": "Чужой"}, os.environ["HUB_BOT_TOKEN"]
        )
    }
    async with client() as c:
        # незарегистрированный пользователь отсекается ещё на авторизации
        r = await c.post(f"/api/seller/bots/{bot_id}/disable", headers=init_for())
        assert r.status_code == 403

        # зарегистрированный, но чужой продавец — 404 по владению магазином
        await make_seller(db, telegram_id=222)
        other_headers = init_for()
        r1 = await c.post(f"/api/seller/bots/{bot_id}/disable", headers=other_headers)
        r2 = await c.post(f"/api/seller/bots/{bot_id}/enable", headers=other_headers)
        r3 = await c.delete(f"/api/seller/bots/{bot_id}", headers=other_headers)
        assert {r1.status_code, r2.status_code, r3.status_code} == {404}


@pytest.mark.asyncio
async def test_connect_message_has_open_shop_button(db):
    await make_seller(db)
    fake_settings = SimpleNamespace(effective_webapp_url="https://app.example")
    with patch("app.api.seller.get_settings", return_value=fake_settings):
        with mock_get_me(), mocked_notify() as notify:
            async with client() as c:
                r = await c.post("/api/seller/bots", json={"token": VALID_TOKEN}, headers=seller_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"]

    button = notify.await_args.kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.text == "🏪 Открыть магазин"
    assert button.web_app.url == f"https://app.example/shop/{body['bot']['id']}"
