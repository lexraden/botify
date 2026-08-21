from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Payout, PayoutBatch, Seller
from app.payments.payouts import send_payout
from tests.test_api import buyer_headers, client, seller_headers, setup_shop
from tests.test_payments import make_order, patched_notifications


async def paid_physical_order(db) -> tuple[int, int]:
    """Оплаченный физический заказ через API + webhook-обработчик."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
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
    bot_id, order_id = await paid_physical_order(db)

    with patch("app.payments.service._notify", new=AsyncMock()) as notify_mock:
        async with client() as c:
            # пустой fulfillment отклоняется
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill", headers=seller_headers(), json={}
            )
            assert r.status_code == 400

            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"tracking": "RA123456789CN", "note": "Отправлено CDEK"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "delivered"

            # повторная отправка уже доставленного — отказ
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
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
    assert fake_crypto.transfer.call_args.kwargs["spend_id"].startswith("batch-")
    assert fake_crypto.transfer.call_args.kwargs["amount"] == pytest.approx(92.0)

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


async def _paid_order_payout(db) -> int:
    """Оплаченный заказ -> id его выплаты."""
    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)
    async with db() as session:
        return (await session.execute(select(Payout))).scalar_one().id


def _settings_with(**overrides):
    from app.config import get_settings

    # payouts.py импортирует get_settings по имени — патчим там, где он вызывается
    return patch(
        "app.payments.payouts.get_settings",
        return_value=get_settings().model_copy(update=overrides),
    )


@pytest.mark.asyncio
async def test_payout_below_minimum_accumulates_silently(db):
    """Мелкая выплата не уходит и не будит продавца ошибкой — она копится."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("1"))
    payout_id = await _paid_order_payout(db)

    fake_crypto = SimpleNamespace(transfer=AsyncMock())
    with (
        _settings_with(min_payout_usdt=10.0),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        assert await send_payout(payout_id) is False

    assert fake_crypto.transfer.await_count == 0  # заведомо провальный transfer не делаем
    assert hub_mock.await_count == 0  # и продавца не тревожим
    async with db() as session:
        payout = await session.get(Payout, payout_id)
        assert payout.status == "pending" and payout.batch_id is None


@pytest.mark.asyncio
async def test_payouts_of_several_orders_go_in_one_transfer(db):
    """Накопленное уходит одним переводом на всю сумму."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("1"))
    await _paid_order_payout(db)
    await make_order(
        db, product_type="physical", digital_url=None, total=Decimal("1"), invoice_id=555002
    )

    from app.payments.payouts import flush_seller_payouts

    p1, p2 = patched_notifications()
    with p1, p2:
        from app.payments.service import handle_invoice_paid

        await handle_invoice_paid(555002, None)

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=4242))
    )
    with (
        _settings_with(min_payout_usdt=1.5),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        async with db() as session:
            seller_id = (await session.execute(select(Seller))).scalars().first().id
        assert await flush_seller_payouts(seller_id) is True

    assert fake_crypto.transfer.await_count == 1
    assert fake_crypto.transfer.call_args.kwargs["amount"] == pytest.approx(1.84)  # 2 × 0.92
    assert "1.84" in hub_mock.call_args.args[1]

    async with db() as session:
        payouts = (await session.execute(select(Payout))).scalars().all()
        assert {p.status for p in payouts} == {"sent"}
        assert {p.transfer_id for p in payouts} == {4242}


@pytest.mark.asyncio
async def test_amount_too_small_releases_batch_for_later(db):
    """Если минимум Crypto Pay выше нашего — пачка распускается, деньги копятся."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("1"))
    payout_id = await _paid_order_payout(db)

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(side_effect=Exception("CodeErrorFactory_400: [400] AMOUNT_TOO_SMALL"))
    )
    with (
        _settings_with(min_payout_usdt=0.5),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        assert await send_payout(payout_id) is False

    assert hub_mock.await_count == 0  # продавцу это знать незачем
    async with db() as session:
        payout = await session.get(Payout, payout_id)
        assert payout.status == "pending"  # не failed: ретрай подберёт
        assert payout.batch_id is None  # пачка распущена, сумма растёт дальше
        batch = (await session.execute(select(PayoutBatch))).scalar_one()
        assert batch.status == "too_small" and "AMOUNT_TOO_SMALL" in batch.last_error


@pytest.mark.asyncio
async def test_provider_fee_comes_off_the_seller_share(db):
    """Комиссия Crypto Pay идёт сверх нашей и уменьшает долю продавца."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))

    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        # Crypto Pay сообщил, что удержал 3 USDT со стодолларового платежа
        await handle_invoice_paid(555001, None, fee_amount=Decimal("3"))

    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        assert Decimal(payout.commission) == Decimal("5.000000")   # наши 5% целиком
        assert Decimal(payout.provider_fee) == Decimal("3.000000")
        assert Decimal(payout.amount) == Decimal("92.000000")      # 100 − 5 − 3


@pytest.mark.asyncio
async def test_provider_fee_falls_back_to_configured_rate(db):
    """Если вебхук не прислал комиссию — считаем по ставке, а не в ноль."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))

    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)

    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        assert Decimal(payout.provider_fee) == Decimal("3.000000")  # 3% по умолчанию
        assert Decimal(payout.amount) == Decimal("92.000000")


@pytest.mark.asyncio
async def test_seller_message_shows_two_decimals(db):
    """В чат уходит «1.00 USDT», а не «1.000000»."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("1"))

    from app.payments.service import handle_invoice_paid

    with (
        patch("app.payments.service._notify", new=AsyncMock()),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        await handle_invoice_paid(555001, None)

    text = hub_mock.call_args.args[1]
    assert "1.00 USDT" in text and "1.000000" not in text


@pytest.mark.asyncio
async def test_withdraw_button_flow(db):
    """Кнопка «Вывести»: копится — отказ, набралось — перевод уходит."""
    from tests.test_api import client, seller_headers

    await make_order(db, product_type="physical", digital_url=None, total=Decimal("1"))
    p1, p2 = patched_notifications()
    with p1, p2:
        from app.payments.service import handle_invoice_paid

        await handle_invoice_paid(555001, None)

    # 1 USDT − 5% − 3% = 0.92, до минимума в 2 USDT не хватает
    async with client() as c:
        r = await c.post("/api/seller/payouts/withdraw", headers=seller_headers())
        body = r.json()
    assert body["ok"] is False and body["reason"] == "below_min"
    assert float(body["pending"]) == pytest.approx(0.92)

    # добираем вторую продажу — теперь накоплено больше минимума
    await make_order(
        db, product_type="physical", digital_url=None, total=Decimal("5"), invoice_id=555002
    )
    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555002, None)

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=99001))
    )
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        async with client() as c:
            r = await c.post("/api/seller/payouts/withdraw", headers=seller_headers())
            body = r.json()

    assert body["ok"] is True
    assert float(body["sent"]) == pytest.approx(5.52)  # 0.92 + 4.60
    assert float(body["pending"]) == 0
    assert fake_crypto.transfer.await_count == 1

    # повторное нажатие уже ничего не отправляет
    with patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto):
        async with client() as c:
            r = await c.post("/api/seller/payouts/withdraw", headers=seller_headers())
    assert r.json()["reason"] == "no_funds"
    assert fake_crypto.transfer.await_count == 1
