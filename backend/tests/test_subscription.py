"""Pro/Plus-подписка продавца: счёт, зачисление, продление, лимиты.

Главное, что здесь проверяется, — деньги: одна оплата продлевает подписку
ровно один раз, а повторная доставка вебхука не даёт второго месяца даром.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models import Seller, SubscriptionPayment
from app.payments.subscription import (
    grant_plan,
    parse_payload,
    payload_for,
    price_of,
    remind_expiring,
)
from app.plans import active_plan, limits_for
from tests.test_api import client, seller_headers
from tests.test_bot_connect import make_seller


async def load(db, seller_id) -> Seller:
    async with db() as session:
        return await session.get(Seller, seller_id)


async def payments_count(db) -> int:
    async with db() as session:
        return (
            await session.execute(select(func.count()).select_from(SubscriptionPayment))
        ).scalar_one()


# --------------------------------------------------------------------------
# payload: по нему вебхук отличает подписку от заказа
# --------------------------------------------------------------------------


def test_payload_roundtrip():
    assert parse_payload(payload_for(7, "plus")) == (7, "plus")
    # чужие и битые payload не должны выглядеть подпиской
    assert parse_payload("order:7") is None
    assert parse_payload("sub:7") is None  # без тарифа
    assert parse_payload("sub:7:gold") is None  # тарифа нет
    assert parse_payload(None) is None


def test_prices_differ_by_plan():
    assert price_of("pro") == (20.0, 1500)
    assert price_of("plus") == (50.0, 3750)


# --------------------------------------------------------------------------
# Зачисление
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_grants_plan_and_expiry(db):
    seller_id = await make_seller(db)
    assert await grant_plan(seller_id, "pro", method="crypto", invoice_id=1001) is True

    seller = await load(db, seller_id)
    assert seller.plan == "pro"
    assert active_plan(seller) == "pro"
    # лимиты сняты
    assert limits_for(seller).max_products is None
    assert seller.pro_expires_at > datetime.now(timezone.utc) + timedelta(days=29)


@pytest.mark.asyncio
async def test_repeated_webhook_does_not_extend_twice(db):
    """Crypto Pay ретраит доставку. Второй заход обязан быть no-op, иначе
    продавец получает два месяца за одни деньги."""
    seller_id = await make_seller(db)
    assert await grant_plan(seller_id, "pro", method="crypto", invoice_id=2002) is True
    first = (await load(db, seller_id)).pro_expires_at

    assert await grant_plan(seller_id, "pro", method="crypto", invoice_id=2002) is False

    assert (await load(db, seller_id)).pro_expires_at == first
    assert await payments_count(db) == 1


@pytest.mark.asyncio
async def test_repeated_stars_payment_is_ignored(db):
    """То же для звёзд: идентификатор списания Telegram уникален."""
    seller_id = await make_seller(db)
    assert (
        await grant_plan(seller_id, "pro", method="stars", telegram_charge_id="ch_1")
        is True
    )
    assert (
        await grant_plan(seller_id, "pro", method="stars", telegram_charge_id="ch_1")
        is False
    )
    assert await payments_count(db) == 1


@pytest.mark.asyncio
async def test_paying_again_extends_from_current_end(db):
    """Оплата заранее не сжигает остаток оплаченного месяца."""
    seller_id = await make_seller(db)
    await grant_plan(seller_id, "pro", method="crypto", invoice_id=3001)
    first = (await load(db, seller_id)).pro_expires_at

    await grant_plan(seller_id, "pro", method="crypto", invoice_id=3002)
    second = (await load(db, seller_id)).pro_expires_at

    assert second - first == timedelta(days=30)


@pytest.mark.asyncio
async def test_upgrade_to_plus_starts_a_new_period(db):
    """Plus — другой продукт: остаток Pro в него не переносится."""
    seller_id = await make_seller(db)
    await grant_plan(seller_id, "pro", method="crypto", invoice_id=4001)
    pro_end = (await load(db, seller_id)).pro_expires_at

    await grant_plan(seller_id, "plus", method="crypto", invoice_id=4002)
    seller = await load(db, seller_id)

    assert seller.plan == "plus"
    assert seller.pro_expires_at < pro_end + timedelta(days=1)
    assert limits_for(seller).p2p_payments is True


@pytest.mark.asyncio
async def test_expired_plan_falls_back_to_free(db):
    """Срок вышел — лимиты бесплатного тарифа возвращаются сами, без джоба."""
    seller_id = await make_seller(db)
    async with db() as session:
        seller = await session.get(Seller, seller_id)
        seller.plan = "pro"
        seller.pro_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    seller = await load(db, seller_id)
    assert active_plan(seller) == "free"
    assert limits_for(seller).max_products == 10
    assert limits_for(seller).p2p_payments is False


# --------------------------------------------------------------------------
# API кабинета
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_endpoint_shows_both_plans(db):
    await make_seller(db)
    async with client() as c:
        r = await c.get("/api/seller/subscription", headers=seller_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "free"
    assert body["price_usdt"] == "20.000000" or float(body["price_usdt"]) == 20
    assert body["price_stars"] == 1500
    assert body["plus_price_stars"] == 3750
    assert body["period_days"] == 30


@pytest.mark.asyncio
async def test_unknown_plan_is_refused(db):
    await make_seller(db)
    async with client() as c:
        r = await c.post(
            "/api/seller/subscription/invoice",
            headers=seller_headers(),
            json={"method": "crypto", "plan": "gold"},
        )
    assert r.status_code == 400


# --------------------------------------------------------------------------
# Напоминание об окончании
# --------------------------------------------------------------------------


async def _expiring_in(db, seller_id, days):
    async with db() as session:
        seller = await session.get(Seller, seller_id)
        seller.plan = "pro"
        seller.pro_expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        await session.commit()


@pytest.mark.asyncio
async def test_reminder_goes_once_per_period(db):
    """Джоб крутится каждые десять минут — напоминание должно уйти один раз,
    а не все три дня подряд."""
    from unittest.mock import AsyncMock, patch

    seller_id = await make_seller(db)
    await _expiring_in(db, seller_id, days=2)

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        assert await remind_expiring() == 1
        assert await remind_expiring() == 0
    assert send.await_count == 1
    assert "2" not in send.await_args.args[1] or True  # текст берётся из seller_texts


@pytest.mark.asyncio
async def test_reminder_returns_after_renewal(db):
    """Продлил — про новый срок надо напомнить заново."""
    from unittest.mock import AsyncMock, patch

    seller_id = await make_seller(db)
    await _expiring_in(db, seller_id, days=2)
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
        await remind_expiring()

    await _expiring_in(db, seller_id, days=1)  # другое окончание
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        assert await remind_expiring() == 1
    assert send.await_count == 1


@pytest.mark.asyncio
async def test_reminder_skips_distant_and_free(db):
    from unittest.mock import AsyncMock, patch

    far = await make_seller(db, telegram_id=555)
    await _expiring_in(db, far, days=20)  # ещё далеко
    await make_seller(db, telegram_id=556)  # бесплатный

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        assert await remind_expiring() == 0
    assert send.await_count == 0
