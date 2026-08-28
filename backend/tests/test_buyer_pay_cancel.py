"""Оплата и отмена своего неоплаченного заказа покупателем
и фильтр неоплаченных из списка заказов продавца."""

from datetime import timedelta

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
        json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": pid, "qty": 1}]},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_pay_returns_fresh_invoice_link(db, monkeypatch):
    async def fake_invoice(order_id, total, shop=None):
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
    async def boom(order_id, total, shop=None):
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
    """Отменённый заказ исчезает из «Моих покупок», но строка в базе остаётся:
    сверка платежей и статистика продолжают её видеть."""
    bot_id = await setup_shop(db)
    async with client() as c:
        oid = await create_order(c, bot_id)
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/cancel", headers=buyer_headers())
        assert r.status_code == 200, r.text
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        assert r.json() == []
        async with db() as session:
            order = await session.get(Order, oid)
            assert order.status == "cancelled"


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
        assert by_id == {paid: "paid"}  # отменённый покупателю не показывается


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


@pytest.mark.asyncio
async def test_order_gets_expiry_on_create(db):
    """Созданный заказ живёт unpaid_order_ttl_minutes и отдаёт срок покупателю."""
    bot_id = await setup_shop(db)
    async with client() as c:
        oid = await create_order(c, bot_id)
        async with db() as session:
            order = await session.get(Order, oid)
            assert order.expires_at is not None
            ttl = (order.expires_at - order.created_at).total_seconds()
            assert ttl == pytest.approx(60 * 60, abs=10)  # дефолт — час
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        assert r.json()[0]["expires_at"] is not None


@pytest.mark.asyncio
async def test_pay_resets_expiry_clock(db, monkeypatch):
    """Новый счёт по кнопке «Оплатить» продлевает жизнь заказа: нажал на 59-й
    минуте — получил новый час, а не минуту. Провалившийся инвойс не продлевает."""
    async def fake_invoice(order_id, total, shop=None):
        return f"https://t.me/CryptoBot?start=inv{order_id}"

    async def boom(order_id, total, shop=None):
        raise RuntimeError("crypto down")

    bot_id = await setup_shop(db)
    async with client() as c:
        oid = await create_order(c, bot_id)
        async with db() as session:
            order = await session.get(Order, oid)
            order.expires_at = order.created_at  # почти истёк
            await session.commit()

        monkeypatch.setattr("app.payments.service.create_invoice_for_order", boom)
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/pay", headers=buyer_headers())
        assert r.status_code == 502

        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/pay", headers=buyer_headers())
        assert r.status_code == 502
        async with db() as session:
            order = await session.get(Order, oid)
            assert order.expires_at == order.created_at  # счёт не выписан — не продлили

        monkeypatch.setattr("app.payments.service.create_invoice_for_order", fake_invoice)
        r = await c.post(f"/api/store/{bot_id}/orders/{oid}/pay", headers=buyer_headers())
        assert r.status_code == 200, r.text
        async with db() as session:
            order = await session.get(Order, oid)
            assert order.expires_at > order.created_at
            ttl = (order.expires_at - order.created_at).total_seconds()
            assert ttl == pytest.approx(60 * 60, abs=10)


@pytest.mark.asyncio
async def test_job_cancels_expired_orders(db, monkeypatch):
    """Джоб отменяет просроченный pending_payment и снимает счёт; живой заказ
    и оплаченный не трогаются."""
    from app.services.order_health import expire_unpaid_orders

    async def fake_invoice(order_id, total, shop=None):
        return f"https://t.me/CryptoBot?start=inv{order_id}"

    monkeypatch.setattr("app.payments.service.create_invoice_for_order", fake_invoice)
    discarded = []

    async def fake_discard(invoice_id):
        discarded.append(invoice_id)
        return True

    monkeypatch.setattr(
        # джоб импортирует discard_invoice из payments.service при вызове
        "app.payments.service.discard_invoice",
        fake_discard,
    )

    bot_id = await setup_shop(db)
    async with client() as c:
        expired = await create_order(c, bot_id)
        fresh = await create_order(c, bot_id)
        paid = await create_order(c, bot_id)

    async with db() as session:
        old = await session.get(Order, expired)
        old.expires_at = old.created_at - timedelta(hours=1)  # истёк час назад
        await session.commit()
        order = await session.get(Order, paid)
        order.status = "paid"
        order.expires_at = order.created_at  # оплачен после срока — не трогаем
        await session.commit()

    assert await expire_unpaid_orders() == 1

    async with db() as session:
        assert (await session.get(Order, expired)).status == "cancelled"
        assert (await session.get(Order, fresh)).status == "pending_payment"
        assert (await session.get(Order, paid)).status == "paid"
        # счёт снят ровно у истёкшего
        assert discarded == [(await session.get(Order, expired)).invoice_id]

    # отменённый джобом исчез из «Моих покупок»
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        by_id = {o["id"]: o["status"] for o in r.json()}
        assert by_id == {fresh: "pending_payment", paid: "paid"}
