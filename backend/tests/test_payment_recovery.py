"""Три способа потерять платёж молча — и то, что им теперь мешает.

Общая беда была одна: деньги приняты, а заказ этого не заметил, и никто не
узнал. Возврата в MVP нет, поэтому каждый такой случай разбирается руками —
дешевле не допускать.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Order
from tests.test_api import buyer_headers, client, seller_headers, setup_shop


async def _pending_order(c, bot_id: int, invoice_id: int = 900100) -> int:
    """Неоплаченный заказ с проставленным счётом."""
    r = await c.post(
        f"/api/seller/bots/{bot_id}/products",
        headers=seller_headers(),
        json={"type": "physical", "title": "Кружка", "price": "5"},
    )
    pid = r.json()["id"]
    r = await c.post(
        f"/api/store/{bot_id}/orders",
        headers=buyer_headers(),
        json={
            "items": [{"product_id": pid, "qty": 1}],
            "delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"},
        },
    )
    assert r.status_code == 200, r.text
    order_id = r.json()["id"]

    from app.db import get_session

    async with get_session() as session:
        order = await session.get(Order, order_id)
        order.invoice_id = invoice_id
        await session.commit()
    return order_id


# --------------------------------------------------------------------------
# 1. Отмена снимает счёт: по оставшейся ссылке заплатить уже нельзя
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_kills_the_invoice(db):
    """Ссылка на оплату остаётся у покупателя в переписке с @CryptoBot.
    Если её не снять, оплата отменённого заказа пройдёт мимо всего."""
    bot_id = await setup_shop(db)
    deleted: list[int] = []
    fake = SimpleNamespace(delete_invoice=AsyncMock(side_effect=lambda i: deleted.append(i)))

    async with client() as c:
        order_id = await _pending_order(c, bot_id)
        with patch("app.payments.service.get_crypto_pay", return_value=fake):
            r = await c.post(f"/api/store/{bot_id}/orders/{order_id}/cancel", headers=buyer_headers())
    assert r.status_code == 200, r.text
    assert deleted == [900100]


@pytest.mark.asyncio
async def test_cancel_survives_failed_invoice_removal(db):
    """Crypto Pay недоступен — отмену это откатывать не должно: счёт протухнет
    сам через час, а покупатель своё действие уже совершил."""
    bot_id = await setup_shop(db)
    fake = SimpleNamespace(delete_invoice=AsyncMock(side_effect=Exception("network")))

    async with client() as c:
        order_id = await _pending_order(c, bot_id)
        with patch("app.payments.service.get_crypto_pay", return_value=fake):
            r = await c.post(f"/api/store/{bot_id}/orders/{order_id}/cancel", headers=buyer_headers())
    assert r.status_code == 200, r.text

    async with db() as session:
        assert (await session.get(Order, order_id)).status == "cancelled"


# --------------------------------------------------------------------------
# 2. «Оплатить» не плодит живые счета
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeated_pay_discards_previous_invoice(db):
    """У заказа должен оставаться ровно один оплачиваемый счёт: на этом
    инварианте держится сверка, и без него оплата второй ссылки пропадает."""
    bot_id = await setup_shop(db)
    deleted: list[int] = []
    fake = SimpleNamespace(delete_invoice=AsyncMock(side_effect=lambda i: deleted.append(i)))

    async def fake_invoice(order_id, total, shop=None):
        # invoice_id заказу пишет сам эндпоинт, в своей транзакции: своей
        # сессией сюда лезть нельзя — заказ уже под FOR UPDATE, и вложенный
        # UPDATE встал бы в очередь за блокировкой вызывающего
        return 900200, "https://t.me/CryptoBot?start=inv2"

    async with client() as c:
        order_id = await _pending_order(c, bot_id)
        with (
            patch("app.payments.service.get_crypto_pay", return_value=fake),
            patch("app.payments.service.create_invoice_for_order", new=fake_invoice),
        ):
            r = await c.post(f"/api/store/{bot_id}/orders/{order_id}/pay", headers=buyer_headers())
    assert r.status_code == 200, r.text
    assert deleted == [900100]  # прежний счёт снят до выдачи нового


# --------------------------------------------------------------------------
# 3. Вебхук просит повторить, а не делает вид, что справился
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_asks_for_retry_when_handling_fails(db):
    """Раньше любой сбой обработки выглядел для Crypto Pay успехом, и повтора
    не было: деньги приняты, заказ навсегда pending_payment."""
    import json

    body = json.dumps(
        {"update_type": "invoice_paid", "payload": {"invoice_id": 1, "payload": "order:1"}}
    ).encode()

    with (
        patch("app.main.verify_webhook_signature", return_value=True),
        patch("app.main.handle_invoice_paid", new=AsyncMock(side_effect=Exception("БД легла"))),
    ):
        async with client() as c:
            r = await c.post(
                "/webhook/cryptopay", content=body, headers={"crypto-pay-api-signature": "x"}
            )
    assert r.status_code == 500


@pytest.mark.asyncio
async def test_webhook_stays_ok_when_invoice_is_unknown(db):
    """Неизвестный счёт — не повод просить повтор: повторять нечего."""
    import json

    body = json.dumps(
        {"update_type": "invoice_paid", "payload": {"invoice_id": 424242, "payload": None}}
    ).encode()

    with patch("app.main.verify_webhook_signature", return_value=True):
        async with client() as c:
            r = await c.post(
                "/webhook/cryptopay", content=body, headers={"crypto-pay-api-signature": "x"}
            )
    assert r.status_code == 200


# --------------------------------------------------------------------------
# 4. Сверка добирает оплату, о которой вебхук не сообщил
# --------------------------------------------------------------------------


def _paid_invoice(invoice_id: int, order_id: int):
    return SimpleNamespace(
        invoice_id=invoice_id,
        status="paid",
        payload=f"order:{order_id}",
        fee_amount=None,
        fee_asset=None,
    )


@pytest.mark.asyncio
async def test_reconcile_recovers_payment_without_webhook(db):
    """Вебхук не дошёл вовсе (не прописан URL, лежал деплой). Без сверки
    покупатель считает, что заплатил, а продавец заказа не видит."""
    from app.payments.reconcile import reconcile_paid_invoices

    bot_id = await setup_shop(db)
    async with client() as c:
        order_id = await _pending_order(c, bot_id)

    fake = SimpleNamespace(get_invoices=AsyncMock(return_value=[_paid_invoice(900100, order_id)]))
    with (
        patch("app.payments.reconcile.get_crypto_pay", return_value=fake),
        patch("app.payments.service._notify", new=AsyncMock()),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        assert await reconcile_paid_invoices() == 1

    async with db() as session:
        assert (await session.get(Order, order_id)).status == "paid"


@pytest.mark.asyncio
async def test_reconcile_is_idempotent_with_late_webhook(db):
    """Опоздавший вебхук и сверка могут прийти к одному заказу. Кто первый —
    того и заказ; второй видит статус не pending_payment и ничего не делает."""
    from app.payments.reconcile import reconcile_paid_invoices

    bot_id = await setup_shop(db)
    async with client() as c:
        order_id = await _pending_order(c, bot_id)

    fake = SimpleNamespace(get_invoices=AsyncMock(return_value=[_paid_invoice(900100, order_id)]))
    with (
        patch("app.payments.reconcile.get_crypto_pay", return_value=fake),
        patch("app.payments.service._notify", new=AsyncMock()),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        assert await reconcile_paid_invoices() == 1
        assert await reconcile_paid_invoices() == 0  # второй проход не задваивает

    from app.models import Payout

    async with db() as session:
        payouts = (await session.execute(select(Payout))).scalars().all()
    assert len(payouts) == 1  # доля продавца начислена ровно один раз


@pytest.mark.asyncio
async def test_reconcile_leaves_unpaid_alone(db):
    """Неоплаченный счёт сверка не трогает — иначе она сама создавала бы
    выплаты из воздуха."""
    from app.payments.reconcile import reconcile_paid_invoices

    bot_id = await setup_shop(db)
    async with client() as c:
        order_id = await _pending_order(c, bot_id)

    unpaid = SimpleNamespace(invoice_id=900100, status="active", payload=f"order:{order_id}")
    fake = SimpleNamespace(get_invoices=AsyncMock(return_value=[unpaid]))
    with patch("app.payments.reconcile.get_crypto_pay", return_value=fake):
        assert await reconcile_paid_invoices() == 0

    async with db() as session:
        assert (await session.get(Order, order_id)).status == "pending_payment"


@pytest.mark.asyncio
async def test_reconcile_survives_crypto_pay_outage(db):
    """Crypto Pay недоступен — цикл обслуживания не должен падать."""
    from app.payments.reconcile import reconcile_paid_invoices

    bot_id = await setup_shop(db)
    async with client() as c:
        await _pending_order(c, bot_id)

    fake = SimpleNamespace(get_invoices=AsyncMock(side_effect=Exception("503")))
    with patch("app.payments.reconcile.get_crypto_pay", return_value=fake):
        assert await reconcile_paid_invoices() == 0


# --------------------------------------------------------------------------
# 5. Физический заказ без адреса не оформляется
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_physical_order_requires_delivery(db):
    """Без адреса продавец не может отправить посылку и идёт выяснять его в
    чат с каждым покупателем."""
    bot_id = await setup_shop(db)
    async with client() as c:
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
        assert r.status_code == 400
        assert r.json()["detail"] == "delivery_required"

        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": pid, "qty": 1}],
                "delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"},
            },
        )
        assert r.status_code == 200, r.text
        order_id = r.json()["id"]

        # продавец видит адрес — иначе весь смысл теряется
        r = await c.get(f"/api/seller/bots/{bot_id}/orders", headers=seller_headers())
        assert r.status_code == 200
    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.delivery == {
            "name": "Аня",
            "phone": "+79990001122",
            "address": "Тверская 1",
        }


@pytest.mark.asyncio
async def test_digital_order_does_not_ask_for_address(db):
    """Цифровой заказ везти некуда — лишние поля в чекауте стоят конверсии."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={
                "type": "digital",
                "title": "Гайд",
                "price": "5",
                "digital_content": {"url": "https://x.example/g"},
            },
        )
        pid = r.json()["id"]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={"items": [{"product_id": pid, "qty": 1}]},
        )
        assert r.status_code == 200, r.text
        order_id = r.json()["id"]

    async with db() as session:
        assert (await session.get(Order, order_id)).delivery is None
