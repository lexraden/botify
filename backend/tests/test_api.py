import os
import time

import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy import select

from app.models import Order, Seller, SellerBot
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
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Бургер", "price": "4.99"},
        )
        assert r.status_code == 200, r.text
        burger_id = r.json()["id"]
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
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

        # покупатель заказ видит сразу...
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        assert [o["id"] for o in r.json()] == [order["id"]]
        # ...а продавец нет: неоплаченная корзина в его список не попадает
        r = await c.get(f"/api/seller/bots/{bot_id}/orders", headers=seller_headers())
        assert r.json() == []

        # «вебхук» оплаты перевёл заказ в paid — теперь он рабочий для продавца
        async with db() as session:
            paid_order = await session.get(Order, order["id"])
            paid_order.status = "paid"
            await session.commit()
        r = await c.get(f"/api/seller/bots/{bot_id}/orders", headers=seller_headers())
        seller_orders = r.json()
        assert [o["id"] for o in seller_orders] == [order["id"]]
        assert seller_orders[0]["comment"] == "без лука"
        # сервис анонимный: личности покупателя в заказах продавца быть не должно
        assert "customer_username" not in seller_orders[0]
        assert "customer_first_name" not in seller_orders[0]
        assert "petya" not in str(seller_orders)
        assert seller_orders[0]["created_at"]

        # продавец видит состав заказа: что, сколько и по какой цене куплено
        items = seller_orders[0]["items"]
        assert {(i["title"], i["qty"]) for i in items} == {("Бургер", 2), ("Гайд", 1)}
        burger = next(i for i in items if i["title"] == "Бургер")
        assert float(burger["price"]) == pytest.approx(4.99)
        assert seller_orders[0]["fulfillment"] is None  # заказ ещё не отправлен

        # статистика продавца
        r = await c.get("/api/seller/me", headers=seller_headers())
        me = r.json()
        assert [b["id"] for b in me["bots"]] == [bot_id]

        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        summary = r.json()
        assert summary["customers_count"] == 1
        assert summary["orders_count"] == 1


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
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кофе", "price": "3"},
        )
        pid = r.json()["id"]
        await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"items": [{"product_id": pid, "qty": 1}]},
        )
        r = await c.delete(f"/api/seller/bots/{bot_id}/products/{pid}", headers=seller_headers())
        assert r.json()["status"] == "deactivated"
        # с витрины товар пропал
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert r.json()["products"] == []


@pytest.mark.asyncio
async def test_connect_bot_notifies_seller_in_hub(db):
    """После подключения бота продавцу приходит подтверждение в hub-бот."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    async with db() as session:
        session.add(Seller(telegram_id=SELLER_TG["id"]))
        await session.commit()

    token = "555666777:AAconnect-via-api-token-aaaaaaaaaa"
    with (
        patch(
            "app.services.bot_connect.Bot.get_me",
            new=AsyncMock(return_value=SimpleNamespace(id=555666777, username="new_shop_bot")),
        ),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        async with client() as c:
            r = await c.post("/api/seller/bots", headers=seller_headers(), json={"token": token})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ok"] and body["bot"]["bot_username"] == "new_shop_bot"

    assert hub_mock.await_count == 1
    assert "new_shop_bot" in hub_mock.call_args.args[1]

    # невалидный токен: ни бота, ни уведомления
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock2:
        async with client() as c:
            r = await c.post("/api/seller/bots", headers=seller_headers(), json={"token": "это точно не токен"})
            assert r.json() == {"ok": False, "error": "bad_format", "bot": None}
    assert hub_mock2.await_count == 0


@pytest.mark.asyncio
async def test_payments_health_is_admin_only(db):
    """Диагностика платежей доступна только админу платформы."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    async with db() as session:
        session.add(Seller(telegram_id=SELLER_TG["id"]))
        await session.commit()

    async with client() as c:
        r = await c.get("/api/admin/payments/health", headers=seller_headers())
        assert r.status_code == 403  # обычный продавец не админ

    async with db() as session:
        seller = (await session.execute(select(Seller))).scalar_one()
        seller.is_admin = True
        await session.commit()

    # токен не задан — честно сообщаем, что оплата не настроена
    async with client() as c:
        r = await c.get("/api/admin/payments/health", headers=seller_headers())
        body = r.json()
        assert body["configured"] is False and body["reachable"] is False

    # токен задан и API отвечает — эндпоинт показывает имя приложения
    fake_crypto = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(name="Botify")))
    with patch("app.payments.client.get_crypto_pay", return_value=fake_crypto):
        async with client() as c:
            r = await c.get("/api/admin/payments/health", headers=seller_headers())
            body = r.json()
    assert body["configured"] and body["reachable"] and body["app_name"] == "Botify"
