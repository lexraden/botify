"""Статистика магазина и задел под Pro-тариф."""

from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import Customer, Order, Seller, ShopEvent
from tests.test_api import buyer_headers, client, seller_headers, setup_shop


@contextmanager
def limits_enforced():
    """Включает лимиты тарифа так, как это будет при запуске Pro."""
    from app.config import get_settings

    enforced = get_settings().model_copy(update={"enforce_plan_limits": True})
    with patch("app.config.get_settings", return_value=enforced):
        yield


async def paid_order(db, bot_id: int, customer_id: int, total="10") -> None:
    async with db() as session:
        seller = (await session.execute(select(Seller))).scalars().first()
        session.add(
            Order(
                seller_id=seller.id,
                bot_id=bot_id,
                customer_id=customer_id,
                total=Decimal(total),
                status="paid",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_events_feed_shop_stats(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кофе", "price": "5"},
        )
        product_id = r.json()["id"]

        # покупатель смотрит витрину и товар, доходит до оформления
        await c.post(f"/api/store/{bot_id}/events", headers=buyer_headers(), json={"type": "shop_open"})
        await c.post(
            f"/api/store/{bot_id}/events",
            headers=buyer_headers(),
            json={"type": "product_view", "product_id": product_id},
        )
        await c.post(
            f"/api/store/{bot_id}/events", headers=buyer_headers(), json={"type": "checkout_start"}
        )
        # незнакомый тип не создаёт запись и не роняет запрос
        r = await c.post(
            f"/api/store/{bot_id}/events", headers=buyer_headers(), json={"type": "нечто"}
        )
        assert r.json()["status"] == "ignored"

        r = await c.get(f"/api/seller/bots/{bot_id}/stats", headers=seller_headers())
        stats = r.json()
        assert stats["product_views"] == 1
        assert stats["checkout_starts"] == 1
        assert stats["telegram_users"] == 1
        assert stats["purchases"] == 0
        assert Decimal(stats["total_sales"]) == 0

    async with db() as session:
        events = (await session.execute(select(ShopEvent))).scalars().all()
        assert {e.type for e in events} == {"shop_open", "product_view", "checkout_start"}


@pytest.mark.asyncio
async def test_stats_count_purchases_and_repeat_customers(db):
    bot_id = await setup_shop(db)
    async with db() as session:
        seller = (await session.execute(select(Seller))).scalars().first()
        loyal = Customer(telegram_id=901, seller_id=seller.id, bot_id=bot_id)
        once = Customer(telegram_id=902, seller_id=seller.id, bot_id=bot_id)
        session.add_all([loyal, once])
        await session.commit()
        loyal_id, once_id = loyal.id, once.id

    await paid_order(db, bot_id, loyal_id, "10")
    await paid_order(db, bot_id, loyal_id, "15")
    await paid_order(db, bot_id, once_id, "5")

    async with client() as c:
        r = await c.get(f"/api/seller/bots/{bot_id}/stats", headers=seller_headers())
        stats = r.json()
    assert stats["purchases"] == 3
    assert Decimal(stats["total_sales"]) == 30
    assert stats["repeat_customers"] == 1  # только тот, у кого две покупки


@pytest.mark.asyncio
async def test_plan_usage_reported_but_not_enforced_by_default(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Товар", "price": "5"},
        )
        await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "digital", "title": "Гайд", "price": "5"},
        )
        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        limits = r.json()["limits"]

    assert limits["plan"] == "free"
    assert limits["enforced"] is False  # лимиты пока только показываются
    assert limits["products_used"] == 1 and limits["products_cap"] == 10
    assert limits["services_used"] == 1 and limits["services_cap"] == 10
    assert limits["mailing_recipients_cap"] == 1000


@pytest.mark.asyncio
async def test_free_plan_caps_apply_when_enforcement_is_on(db):
    """Когда Pro запустится: рост блокируется, но ничего не удаляется."""
    bot_id = await setup_shop(db)
    async with client() as c:
        for i in range(10):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/products",
                headers=seller_headers(),
                json={"type": "physical", "title": f"Товар {i}", "price": "5"},
            )
            assert r.status_code == 200

        with limits_enforced():
            r = await c.post(
                f"/api/seller/bots/{bot_id}/products",
                headers=seller_headers(),
                json={"type": "physical", "title": "Одиннадцатый", "price": "5"},
            )
            assert r.status_code == 403
            # услуги — отдельный лимит, они ещё доступны
            r = await c.post(
                f"/api/seller/bots/{bot_id}/products",
                headers=seller_headers(),
                json={"type": "digital", "title": "Гайд", "price": "5"},
            )
            assert r.status_code == 200

        # каталог на месте: лимит не удаляет уже добавленное
        r = await c.get(f"/api/seller/bots/{bot_id}/products", headers=seller_headers())
        assert len(r.json()) == 11


@pytest.mark.asyncio
async def test_mailing_cap_blocks_send_but_keeps_customer_base(db):
    from app.plans import FREE

    bot_id = await setup_shop(db)
    async with db() as session:
        seller = (await session.execute(select(Seller))).scalars().first()
        for i in range(FREE.max_mailing_recipients + 1):
            session.add(Customer(telegram_id=10_000 + i, seller_id=seller.id, bot_id=bot_id))
        await session.commit()

    async with client() as c:
        with limits_enforced():
            r = await c.post(
                f"/api/seller/bots/{bot_id}/mailings",
                headers=seller_headers(),
                json={"text": "Всем привет"},
            )
            assert r.status_code == 403

    async with db() as session:
        customers = (await session.execute(select(Customer))).scalars().all()
        assert len(customers) == FREE.max_mailing_recipients + 1  # база цела
