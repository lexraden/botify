"""Один бот = один магазин: данные магазинов одного продавца не пересекаются."""

import pytest
from sqlalchemy import select

from app.models import Mailing, Order, Seller, SellerBot
from app.security import encrypt_bot_token
from tests.test_api import client, init_data_for, seller_headers

SECOND_BOT_TOKEN = "444555666:AAsecond-shop-token-for-isolation-test"
BUYER_B = {"id": 888, "first_name": "Оля", "username": "olya", "language_code": "ru"}


async def add_second_bot(db) -> int:
    """Второй магазин того же продавца."""
    async with db() as session:
        seller = (await session.execute(select(Seller))).scalars().first()
        bot = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=encrypt_bot_token(SECOND_BOT_TOKEN),
            bot_username="second_bot",
            telegram_bot_id=444555666,
        )
        session.add(bot)
        await session.commit()
        return bot.id


@pytest.mark.asyncio
async def test_two_shops_of_one_seller_are_isolated(db):
    from tests.test_api import setup_shop

    shop_a = await setup_shop(db)
    shop_b = await add_second_bot(db)

    async with client() as c:
        # товар в каждый магазин
        await c.post(
            f"/api/seller/bots/{shop_a}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Товар A", "price": "10"},
        )
        r = await c.post(
            f"/api/seller/bots/{shop_b}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Товар B", "price": "20"},
        )
        product_b = r.json()["id"]

        # каталог кабинета не смешивается
        r = await c.get(f"/api/seller/bots/{shop_a}/products", headers=seller_headers())
        assert [p["title"] for p in r.json()] == ["Товар A"]
        r = await c.get(f"/api/seller/bots/{shop_b}/products", headers=seller_headers())
        assert [p["title"] for p in r.json()] == ["Товар B"]

        # витрина каждого бота показывает только свой каталог
        buyer_b = {"X-Init-Data": init_data_for(BUYER_B, SECOND_BOT_TOKEN)}
        r = await c.get(f"/api/store/{shop_b}", headers=buyer_b)
        assert [p["title"] for p in r.json()["products"]] == ["Товар B"]

        # товар чужого магазина нельзя протащить в заказ
        r = await c.post(
            f"/api/store/{shop_a}/orders",
            headers={"X-Init-Data": init_data_for(BUYER_B, __import__("os").environ["HUB_BOT_TOKEN"])},
            json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": product_b, "qty": 1}]},
        )
        assert r.status_code == 401  # чужая подпись вообще не проходит

        r = await c.post(
            f"/api/store/{shop_b}/orders",
            headers=buyer_b,
            json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": product_b, "qty": 1}]},
        )
        assert r.status_code == 200

        # «вебхук» оплатил единственный заказ — сводка считает оплаченное
        async with db() as session:
            order = (await session.execute(select(Order))).scalars().first()
            order.status = "paid"
            await session.commit()

        # покупатель и заказ учтены только во втором магазине
        r = await c.get(f"/api/seller/bots/{shop_a}/summary", headers=seller_headers())
        assert r.json()["customers_count"] == 0 and r.json()["orders_count"] == 0
        r = await c.get(f"/api/seller/bots/{shop_b}/summary", headers=seller_headers())
        assert r.json()["customers_count"] == 1 and r.json()["orders_count"] == 1

        # заказы в кабинете тоже разделены
        r = await c.get(f"/api/seller/bots/{shop_a}/orders", headers=seller_headers())
        assert r.json() == []


@pytest.mark.asyncio
async def test_mailing_is_scoped_to_one_shop(db):
    from tests.test_api import setup_shop

    shop_a = await setup_shop(db)
    shop_b = await add_second_bot(db)

    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{shop_b}/mailings",
            headers=seller_headers(),
            json={"text": "Только для второго магазина"},
        )
        assert r.status_code == 200, r.text

        r = await c.get(f"/api/seller/bots/{shop_a}/mailings", headers=seller_headers())
        assert r.json() == []
        r = await c.get(f"/api/seller/bots/{shop_b}/mailings", headers=seller_headers())
        assert len(r.json()) == 1

    async with db() as session:
        mailing = (await session.execute(select(Mailing))).scalar_one()
        assert mailing.bot_id == shop_b


@pytest.mark.asyncio
async def test_shop_of_another_seller_is_not_reachable(db):
    from tests.test_api import setup_shop

    shop_a = await setup_shop(db)
    async with db() as session:
        other = Seller(telegram_id=999)
        session.add(other)
        await session.flush()
        bot = SellerBot(
            seller_id=other.id,
            bot_token_encrypted=encrypt_bot_token("777888999:AAforeign-shop-token-aaaaaaaaaaaa"),
            bot_username="foreign_bot",
            telegram_bot_id=777888999,
        )
        session.add(bot)
        await session.commit()
        foreign_shop = bot.id

    async with client() as c:
        # продавец A не видит магазин продавца B
        r = await c.get(f"/api/seller/bots/{foreign_shop}/summary", headers=seller_headers())
        assert r.status_code == 404
        r = await c.post(
            f"/api/seller/bots/{foreign_shop}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Взлом", "price": "1"},
        )
        assert r.status_code == 404
        # свой магазин при этом доступен
        r = await c.get(f"/api/seller/bots/{shop_a}/summary", headers=seller_headers())
        assert r.status_code == 200
