from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Payout
from app.payments.payouts import send_payout
from tests.test_api import buyer_headers, client, seller_headers, setup_shop
from tests.test_payments import make_order, patched_notifications


async def paid_physical_order(db) -> tuple[int, int]:
    """Оплаченный физический заказ через API + webhook-обработчик."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            "/api/seller/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кроссовки", "price": "50"},
        )
        pid = r.json()["id"]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"items": [{"product_id": pid, "qty": 1}]},
        )
        order_id = r.json()["id"]

    from app.db import get_session
    from app.models import Order

    async with get_session() as session:
        order = await session.get(Order, order_id)
        order.invoice_id = 700100
        await session.commit()

    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        assert await handle_invoice_paid(700100, None)
    return bot_id, order_id


@pytest.mark.asyncio
async def test_fulfill_flow(db):
    _, order_id = await paid_physical_order(db)

    with patch("app.payments.service._notify", new=AsyncMock()) as notify_mock:
        async with client() as c:
            # пустой fulfillment отклоняется
            r = await c.post(
                f"/api/seller/orders/{order_id}/fulfill", headers=seller_headers(), json={}
            )
            assert r.status_code == 400

            r = await c.post(
                f"/api/seller/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"tracking": "RA123456789CN", "note": "Отправлено CDEK"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "delivered"

            # повторная отправка уже доставленного — отказ
            r = await c.post(
                f"/api/seller/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"tracking": "x"},
            )
            assert r.status_code == 400

    buyer_text = notify_mock.call_args.args[2]
    assert "RA123456789CN" in buyer_text and "CDEK" in buyer_text


@pytest.mark.asyncio
async def test_send_payout_success_and_idempotent(db):
    await make_order(db, product_type="physical", digital_url=None)
    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)

    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        payout_id = payout.id

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=31337))
    )
    with patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto):
        assert await send_payout(payout_id) is True
        # повторный вызов не делает второй transfer
        assert await send_payout(payout_id) is True
    assert fake_crypto.transfer.await_count == 1
    assert fake_crypto.transfer.call_args.kwargs["spend_id"] == f"payout-{payout_id}"
    assert fake_crypto.transfer.call_args.kwargs["amount"] == pytest.approx(95.0)

    async with db() as session:
        payout = await session.get(Payout, payout_id)
        assert payout.status == "sent"
        assert payout.transfer_id == 31337


@pytest.mark.asyncio
async def test_send_payout_failure_marks_failed_and_notifies(db):
    await make_order(db, product_type="physical", digital_url=None)
    p1, p2 = patched_notifications()
    with p1, p2:
        from app.payments.service import handle_invoice_paid

        await handle_invoice_paid(555001, None)

    async with db() as session:
        payout_id = (await session.execute(select(Payout))).scalar_one().id

    fake_crypto = SimpleNamespace(transfer=AsyncMock(side_effect=Exception("USER_NOT_FOUND")))
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        assert await send_payout(payout_id) is False

    async with db() as session:
        assert (await session.get(Payout, payout_id)).status == "failed"
    assert "CryptoBot" in hub_mock.call_args.args[1]
