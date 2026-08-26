"""Оплата и отмена своего неоплаченного заказа покупателем
и фильтр неоплаченных из списка заказов продавца."""

import pytest

from app.models import Order
from tests.test_api import (
    BUYER,
    SELLER_BOT_TOKEN,
    buyer_headers,
    client,
    init_data_for,
    seller_headers,
    setup_shop,
)

BUYER2 = {"id": 888, "first_name": "Вася", "username": "vasya", "language_code": "ru"}


async def create_order(c, bot_id) -> int:
    """Продавец заводит товар, покупатель оформляет заказ. Возвращает id заказа."""
    r = await c.post(
        f"/api/seller/bots/{bot_id}/products",
        headers=seller_headers(),
        json={"type": "physical", "title": "Кружка", "price": "5"},
    )
    pid = r.json()["id"]
    r = await c.post(
        f"/api/store/{bot_id}/orders",
        headers=buyer_headers(),
        json={"items": [{"product_id": pid, "qty": 1}]},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_pay_returns_fresh_invoice_link(db, monkeypatch):
    async def fake_invoice(order_id, total):
        return f"https://t.me/CryptoBot?start=inv{order_id}"

    monkeypatch.setattr("app.payments.service.create_invoice_for_order", fake_invoice)
    bot_id = await setup_shop(db)
    async with client() as c:
        oid = await create_order(c, bot_id)
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/pay", headers=buyer_headers())
        assert r.status_code == 200, r.text
        assert r.json()["payment_url"] == f"https://t.me/CryptoBot?start=inv{oid}"

        # чужой покупатель по своему initData ничего не узнаёт и не делает:
        # подменённый order_id не раскрывает даже факт существования заказа
        stranger = {"X-Init-Data": init_data_for(BUYER2, SELLER_BOT_TOKEN)}
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/pay", headers=stranger)
        assert r.status_code == 403
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/cancel", headers=stranger)
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_pay_survives_provider_failure_as_502(db, monkeypatch):
    async def boom(order_id, total):
        raise RuntimeError("crypto down")

    monkeypatch.setattr("app.payments.service.create_invoice_for_order", boom)
    bot_id = await setup_shop(db)
    async with client() as c:
        oid = await create_order(c, bot_id)
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/pay", headers=buyer_headers())
        assert r.status_code == 502
        assert r.json()["detail"] == "invoice_failed"


@pytest.mark.asyncio
async def test_paid_order_cannot_be_paid_or_cancelled(db):
    """Оплаченный заказ кнопкам больше не подчиняется: ретрай/передумал не пойдут."""
    bot_id = await setup_shop(db)
    async with client() as c:
        oid = await create_order(c, bot_id)
        async with db() as session:
            order = await session.get(Order, oid)
            order.status = "paid"
            await session.commit()
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/pay", headers=buyer_headers())
        assert r.status_code == 409
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/cancel", headers=buyer_headers())
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_cancel_moves_pending_to_cancelled(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        oid = await create_order(c, bot_id)
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/cancel", headers=buyer_headers())
        assert r.status_code == 200, r.text
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        by_id = {o["id"]: o["status"] for o in r.json()}
        assert by_id == {oid: "cancelled"}


@pytest.mark.asyncio
async def test_seller_list_hides_pending_only_paid_workflows(db):
    """Два заказа: один отменён покупателем до оплаты, второй оплачен.
    Продавец видит только оплаченный; у покупателя оба со своими статусами."""
    bot_id = await setup_shop(db)
    async with client() as c:
        cancelled = await create_order(c, bot_id)
        paid = await create_order(c, bot_id)
        r = await c.post(
            f"/api/store/{bot_id}/orders/{cancelled}/cancel", headers=buyer_headers()
        )
        assert r.status_code == 200
        async with db() as session:
            order = await session.get(Order, paid)
            order.status = "paid"
            await session.commit()

        r = await c.get(f"/api/seller/bots/{bot_id}/orders", headers=seller_headers())
        assert [o["id"] for o in r.json()] == [paid]

        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        by_id = {o["id"]: o["status"] for o in r.json()}
        assert by_id == {paid: "paid", cancelled: "cancelled"}


@pytest.mark.asyncio
async def test_summary_counts_only_paid_orders(db):
    """Сводка магазина совпадает со списком: orders_count и revenue считают
    только оплаченное — висящая корзина и отмена до оплаты цифру не растят."""
    bot_id = await setup_shop(db)
    async with client() as c:
        cancelled = await create_order(c, bot_id)
        paid = await create_order(c, bot_id)
        await create_order(c, bot_id)  # третья корзина так и остаётся неоплаченной
        r = await c.post(
            f"/api/store/{bot_id}/orders/{cancelled}/cancel", headers=buyer_headers()
        )
        assert r.status_code == 200
        async with db() as session:
            order = await session.get(Order, paid)
            order.status = "paid"
            await session.commit()

        summary = (
            await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        ).json()
        assert summary["orders_count"] == 1
        # выручка живёт на том же наборе статусов PAID_STATUSES — цифры не
        # разъезжаются: три корзины по 5, засчитана одна
        assert float(summary["revenue"]) == pytest.approx(5)
