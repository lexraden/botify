"""Склад: сток товара, списание при оплате, защита от оверселла и гонок."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models import Order, Product
from app.payments.service import handle_invoice_paid
from tests.test_api import buyer_headers, client, seller_headers, setup_shop
from tests.test_payments import patched_notifications


async def _set_invoice(db, order_id: int, invoice_id: int) -> None:
    """Заказ из витрины ещё без инвойса (Crypto Pay в тестах не вызывается)."""
    from app.db import get_session

    async with get_session() as session:
        order = await session.get(Order, order_id)
        order.invoice_id = invoice_id
        await session.commit()


async def stocked_order(db, bot_id: int, stock: int | None, qty: int, invoice_id: int):
    """Товар со стоком и заказ на него через витрину. Возвращает (product_id, order_id)."""
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "stock": stock},
        )
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": pid, "qty": qty}]},
        )
        assert r.status_code == 200, r.text
        order_id = r.json()["id"]

    await _set_invoice(db, order_id, invoice_id)
    return pid, order_id


async def pay(invoice_id: int) -> bool:
    p1, p2 = patched_notifications()
    with p1, p2:
        return await handle_invoice_paid(invoice_id, None)


async def stock_of(db, product_id: int) -> int | None:
    async with db() as session:
        return (await session.get(Product, product_id)).stock


@pytest.mark.asyncio
async def test_paid_order_decrements_stock(db):
    """Обычная покупка: оплата списывает купленное количество."""
    bot_id = await setup_shop(db)
    pid, _order_id = await stocked_order(db, bot_id, stock=5, qty=2, invoice_id=800001)

    assert await pay(800001) is True
    assert await stock_of(db, pid) == 3


@pytest.mark.asyncio
async def test_two_lines_of_same_product_decrement_once_by_sum(db):
    """Один товар двумя строками корзины — списывается суммарно, а не по первой строке."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "stock": 5},
        )
        pid = r.json()["id"]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"},
                "items": [
                    {"product_id": pid, "qty": 1},
                    {"product_id": pid, "qty": 2},
                ],
            },
        )
        assert r.status_code == 200, r.text
        order_id = r.json()["id"]

    await _set_invoice(db, order_id, 800002)
    assert await pay(800002) is True
    assert await stock_of(db, pid) == 2  # 5 − (1 + 2)


@pytest.mark.asyncio
async def test_duplicate_webhook_decrements_once(db):
    """Ретрай вебхука не списывает сток второй раз."""
    bot_id = await setup_shop(db)
    pid, _order_id = await stocked_order(db, bot_id, stock=5, qty=1, invoice_id=800003)

    assert await pay(800003) is True
    assert await pay(800003) is False  # повтор уже no-op

    assert await stock_of(db, pid) == 4


@pytest.mark.asyncio
async def test_unpaid_order_keeps_stock(db):
    """Пока оплата не прошла (и если она не пройдёт) — сток на месте."""
    bot_id = await setup_shop(db)
    pid, _order_id = await stocked_order(db, bot_id, stock=7, qty=2, invoice_id=800004)

    assert await stock_of(db, pid) == 7  # заказ создан — сток не тронут


@pytest.mark.asyncio
async def test_checkout_rejects_more_than_stock(db):
    """Больше остатка в корзину не оформить; ровно остаток — можно."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "stock": 2},
        )
        pid = r.json()["id"]

        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": pid, "qty": 3}]},
        )
        assert r.status_code == 400
        assert "insufficient stock" in r.json()["detail"]

        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": pid, "qty": 2}]},
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_zero_stock_is_visible_but_not_buyable(db):
    """Распроданный товар остаётся на витрине с stock=0, заказ на него отклоняется."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "stock": 0},
        )
        pid = r.json()["id"]

        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        products = {p["id"]: p for p in r.json()["products"]}
        assert products[pid]["stock"] == 0  # витрина видит «нет в наличии»

        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": pid, "qty": 1}]},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_null_stock_stays_null_after_purchase(db):
    """Без стока (NULL) учёт штук не ведётся и покупке ничего не мешает."""
    bot_id = await setup_shop(db)
    pid, _order_id = await stocked_order(db, bot_id, stock=None, qty=3, invoice_id=800005)

    assert await pay(800005) is True
    assert await stock_of(db, pid) is None


@pytest.mark.asyncio
async def test_race_last_unit_never_goes_negative(db):
    """Гонка: два заказа прошли чекаут, пока был один сток.

    Вебхуки обрабатываются последовательно (в проде их сериализует FOR UPDATE,
    SQLite-тест проверяет сам гард): первый платёж забирает последнюю штуку,
    второй оплачивается деньгами, но минус в сток не пишется.
    """
    bot_id = await setup_shop(db)
    _pid_a, order_a = await stocked_order(db, bot_id, stock=1, qty=1, invoice_id=800006)
    pid_b, order_b = await stocked_order(db, bot_id, stock=1, qty=1, invoice_id=800007)
    assert order_a != order_b

    assert await pay(800006) is True  # успел первым — сток 1 → 0
    assert await pay(800007) is True  # деньги приняты, заказ не разворачиваем…

    assert await stock_of(db, pid_b) == 0  # …но и минус не записан


@pytest.mark.asyncio
async def test_stock_survives_product_update_without_stock_field_change(db):
    """Правка товара продавцом (без изменения стока) не сбрасывает и не множит остаток."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "stock": 9},
        )
        pid = r.json()["id"]

        r = await c.put(
            f"/api/seller/bots/{bot_id}/products/{pid}",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка большая", "price": "12", "stock": 9},
        )
        assert r.status_code == 200, r.text
        assert float(r.json()["price"]) == 12

    assert await stock_of(db, pid) == 9


@pytest.mark.asyncio
async def test_negative_or_invalid_stock_rejected_by_api(db):
    """Сток — целое ≥ 0: минус и мусор API не пропускает."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "X", "price": "1", "stock": -1},
        )
        assert r.status_code == 422
