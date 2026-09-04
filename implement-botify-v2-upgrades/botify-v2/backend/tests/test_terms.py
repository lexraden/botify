import os
import time

import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy import select

from app.models import Seller

SELLER_TG = {"id": 4242, "first_name": "Продавец", "username": "terms_seller"}


def init_data_for(user: dict) -> str:
    from app.services.webapp_auth import sign_init_data

    return sign_init_data({"auth_date": int(time.time()), "user": user}, os.environ["HUB_BOT_TOKEN"])


def client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def seller_headers() -> dict:
    return {"X-Init-Data": init_data_for(SELLER_TG)}


async def create_seller(db) -> Seller:
    async with db() as session:
        seller = Seller(telegram_id=SELLER_TG["id"])
        session.add(seller)
        await session.commit()
        await session.refresh(seller)
        return seller


async def seller_of(db) -> Seller:
    async with db() as session:
        result = await session.execute(
            select(Seller).where(Seller.telegram_id == SELLER_TG["id"])
        )
        return result.scalar_one()


@pytest.mark.asyncio
async def test_new_seller_has_not_accepted(db):
    await create_seller(db)
    async with client() as c:
        r = await c.get("/api/seller/me", headers=seller_headers())
        assert r.status_code == 200, r.text
        assert r.json()["terms_accepted"] is False


@pytest.mark.asyncio
async def test_accept_sets_timestamp_and_flag(db):
    await create_seller(db)
    async with client() as c:
        r = await c.post("/api/seller/onboarding/terms-accept", headers=seller_headers())
        assert r.status_code == 200, r.text
        assert r.json()["terms_accepted"] is True

    stored = await seller_of(db)
    assert stored.terms_accepted_at is not None

    # флаг виден и в /me
    async with client() as c:
        r = await c.get("/api/seller/me", headers=seller_headers())
        assert r.json()["terms_accepted"] is True


@pytest.mark.asyncio
async def test_accept_is_idempotent(db):
    """Повторный вызов не перетирает время первого принятия."""
    await create_seller(db)
    async with client() as c:
        await c.post("/api/seller/onboarding/terms-accept", headers=seller_headers())
    first = (await seller_of(db)).terms_accepted_at

    async with client() as c:
        await c.post("/api/seller/onboarding/terms-accept", headers=seller_headers())
    second = (await seller_of(db)).terms_accepted_at

    assert first == second


@pytest.mark.asyncio
async def test_accept_requires_valid_init_data(db):
    await create_seller(db)
    async with client() as c:
        r = await c.post("/api/seller/onboarding/terms-accept")
        assert r.status_code == 401
        r = await c.post(
            "/api/seller/onboarding/terms-accept",
            headers={"X-Init-Data": "hash=deadbeef"},
        )
        assert r.status_code == 401
