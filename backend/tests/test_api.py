import os
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.models import Seller, SellerBot
from app.security import encrypt_bot_token
from app.services.webapp_auth import sign_init_data, validate_init_data

SELLER_BOT_TOKEN = "111222333:AAtest-seller-bot-token-for-api-tests"
BUYER = {"id": 777, "first_name": "Петя", "username": "petya", "language_code": "ru"}
SELLER_TG = {"id": 111, "first_name": "Продавец", "username": "seller1"}


def init_data_for(user: dict, token: str) -> str:
    return sign_init_data({"auth_date": int(time.time()), "user": user}, token)


def test_validate_init_data_round_trip():
    data = init_data_for(BUYER, SELLER_BOT_TOKEN)
    parsed = validate_init_data(data, SELLER_BOT_TOKEN)
    assert parsed is not None and parsed["user"]["id"] == 777
    # чужой токен -> отказ
    assert validate_init_data(data, "999:other-token") is None
    # протухшая подпись -> отказ
    stale = sign_init_data({"auth_date": int(time.time()) - 100000, "user": BUYER}, SELLER_BOT_TOKEN)
    assert validate_init_data(stale, SELLER_BOT_TOKEN) is None


async def setup_shop(db) -> int:
    """Создаёт продавца с ботом. Возвращает bot_id."""
    async with db() as session:
        seller = Seller(telegram_id=SELLER_TG["id"])
        session.add(seller)
        await session.flush()
        bot = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=encrypt_bot_token(SELLER_BOT_TOKEN),
            bot_username="petshop_bot",
            telegram_bot_id=111222333,
        )
        session.add(bot)
        await session.commit()
        return bot.id


def client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def seller_headers() -> dict:
    return {"X-Init-Data": init_data_for(SELLER_TG, os.environ["HUB_BOT_TOKEN"])}


def buyer_headers() -> dict:
    return {"X-Init-Data": init_data_for(BUYER, SELLER_BOT_TOKEN)}


@pytest.mark.asyncio
async def test_store_requires_valid_init_data(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}")
        assert r.status_code == 401
        r = await c.get(f"/api/store/{bot_id}", headers={"X-Init-Data": "hash=deadbeef"})
        assert r.status_code == 401
        r = await c.get("/api/store/9999", headers=buyer_headers())
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_full_buy_flow(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        # продавец добавляет товары через кабинет
        r = await c.post(
            "/api/seller/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Бургер", "price": "4.99"},
        )
        assert r.status_code == 200, r.text
        burger_id = r.json()["id"]
        r = await c.post(
            "/api/seller/products",
            headers=seller_headers(),
            json={"type": "digital", "title": "Гайд", "price": "10", "digital_content": {"url": "https://x"}},
        )
        guide_id = r.json()["id"]

        # покупатель видит витрину (и попадает в базу)
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert r.status_code == 200
        shop = r.json()
        assert shop["shop_name"] == "@petshop_bot"
        assert {p["title"] for p in shop["products"]} == {"Бургер", "Гайд"}

        # оформляет заказ; сумма считается на сервере
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"items": [{"product_id": burger_id, "qty": 2}, {"product_id": guide_id, "qty": 1}], "comment": "без лука"},
        )
        assert r.status_code == 200, r.text
        order = r.json()
        assert order["status"] == "pending_payment"
        assert float(order["total"]) == pytest.approx(19.98)

        # заказ виден покупателю и продавцу
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        assert [o["id"] for o in r.json()] == [order["id"]]
        r = await c.get("/api/seller/orders", headers=seller_headers())
        seller_orders = r.json()
        assert seller_orders[0]["comment"] == "без лука"
        assert seller_orders[0]["customer_username"] == "petya"

        # статистика продавца
        r = await c.get("/api/seller/me", headers=seller_headers())
        me = r.json()
        assert me["customers_count"] == 1
        assert me["orders_count"] == 1


@pytest.mark.asyncio
async def test_order_rejects_foreign_or_inactive_products(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"items": [{"product_id": 12345, "qty": 1}]},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_product_with_orders_deactivates(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            "/api/seller/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кофе", "price": "3"},
        )
        pid = r.json()["id"]
        await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"items": [{"product_id": pid, "qty": 1}]},
        )
        r = await c.delete(f"/api/seller/products/{pid}", headers=seller_headers())
        assert r.json()["status"] == "deactivated"
        # с витрины товар пропал
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert r.json()["products"] == []
