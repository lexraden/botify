"""Профиль покупателя: чтение и правка своего имени (GET/PATCH /store/{bot_id}/me).

Правка обязана жить отдельно от Telegram-имени: first_name перезаписывается
из initData на каждом запросе (upsert_customer), и затёртое там имя не вернуть.
"""

import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.models import Customer
from tests.test_api import (
    BUYER,
    SELLER_BOT_TOKEN,
    buyer_headers,
    client,
    init_data_for,
    seller_headers,
    setup_shop,
)
from tests.test_fulfillment import paid_physical_order


async def _customer(db) -> Customer:
    async with db() as session:
        return (
            await session.execute(
                select(Customer).where(Customer.telegram_id == BUYER["id"])
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_me_returns_telegram_name(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}/me", headers=buyer_headers())
    assert r.status_code == 200, r.text
    assert r.json()["name"] == BUYER["first_name"]
    assert r.json()["telegram_name"] == BUYER["first_name"]


@pytest.mark.asyncio
async def test_rename_and_reset(db):
    """Правка записывается в custom_name, Telegram-имя остаётся нетронутым;
    пустая строка — легальный сброс к нему."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.patch(
            f"/api/store/{bot_id}/me", headers=buyer_headers(), json={"name": "  Алиса  "}
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Алиса"
        assert r.json()["telegram_name"] == BUYER["first_name"]

        customer = await _customer(db)
        assert customer.custom_name == "Алиса"
        assert customer.first_name == BUYER["first_name"]

        r = await c.get(f"/api/store/{bot_id}/me", headers=buyer_headers())
        assert r.json()["name"] == "Алиса"

        r = await c.patch(
            f"/api/store/{bot_id}/me", headers=buyer_headers(), json={"name": "   "}
        )
        assert r.status_code == 200
        assert r.json()["name"] == BUYER["first_name"]

    customer = await _customer(db)
    assert customer.custom_name is None


@pytest.mark.asyncio
async def test_rename_survives_telegram_rename(db):
    """Следующий визит приносит новое Telegram-имя: first_name обновляется,
    своё имя не затирается."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.patch(
            f"/api/store/{bot_id}/me", headers=buyer_headers(), json={"name": "Алиса"}
        )
        assert r.status_code == 200

        renamed = {**BUYER, "first_name": "Пётр"}
        r = await c.get(
            f"/api/store/{bot_id}/me",
            headers={"X-Init-Data": init_data_for(renamed, SELLER_BOT_TOKEN)},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Алиса"
        assert r.json()["telegram_name"] == "Пётр"


@pytest.mark.asyncio
async def test_rename_rejects_too_long(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.patch(
            f"/api/store/{bot_id}/me", headers=buyer_headers(), json={"name": "а" * 65}
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_me_unknown_shop(db):
    async with client() as c:
        r = await c.get("/api/store/9999/me", headers=buyer_headers())
        assert r.status_code == 404
        r = await c.patch("/api/store/9999/me", headers=buyer_headers(), json={"name": "Х"})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_new_review_is_signed_with_custom_name(db):
    """Новый отзыв подписывается именем из профиля. Это снимок на момент
    публикации: правка имени старые отзывы не переписывает."""
    bot_id, order_id = await paid_physical_order(db)

    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        pid = r.json()["products"][0]["id"]
        r = await c.patch(
            f"/api/store/{bot_id}/me", headers=buyer_headers(), json={"name": "Алиса"}
        )
        assert r.status_code == 200

    with (
        patch("app.payments.service._notify", new=AsyncMock()),
        patch("app.api.store.notify_new_review", new=AsyncMock()),
    ):
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"value": "Выдано на кассе"},
            )
            assert r.status_code == 200, r.text
            await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/received", headers=buyer_headers()
            )
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 5}]},
            )
            assert r.status_code == 200, r.text
            assert r.json()[0]["author_name"] == "Алиса"
