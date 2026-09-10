"""Оплата переводом на реквизиты продавца (тариф Pro).

Главное, что здесь проверяется, — денежная часть: по такому заказу платформа
денег не видит, поэтому выплата не заводится и комиссия не берётся. Всё
остальное (сток, выдача цифры, подтверждение покупателю) обязано работать
ровно так же, как при оплате счётом: путь один и тот же.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Order, Payout, Seller, SellerBot
from app.models.payment_methods import ShopPaymentMethod
from tests.test_api import (
    buyer_headers,
    client,
    seller_headers,
    setup_shop,
)


async def make_pro(db, bot_id: int) -> None:
    """Продавцу магазина — действующий Pro (без него p2p недоступен)."""
    async with db() as session:
        bot = await session.get(SellerBot, bot_id)
        seller = await session.get(Seller, bot.seller_id)
        seller.plan = "pro"
        seller.pro_expires_at = None  # бессрочный, выдан вручную
        await session.commit()


async def add_method(db, bot_id: int, **kw) -> int:
    async with db() as session:
        method = ShopPaymentMethod(
            bot_id=bot_id,
            kind=kw.get("kind", "card"),
            label=kw.get("label", "Сбербанк"),
            note=kw.get("note"),
            is_active=kw.get("is_active", True),
        )
        method.account = kw.get("account", "2202 2020 1111 2222")
        method.holder = kw.get("holder", "Иван И.")
        session.add(method)
        await session.commit()
        return method.id


async def add_product(c, bot_id: int, **kw) -> int:
    body = {"type": "physical", "title": "Кружка", "price": "10", "stock": 5}
    body.update(kw)
    r = await c.post(f"/api/seller/bots/{bot_id}/products", headers=seller_headers(), json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# --------------------------------------------------------------------------
# Реквизиты магазина
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_methods_need_pro(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/payment-methods",
            headers=seller_headers(),
            json={"kind": "card", "label": "Сбербанк", "account": "2202"},
        )
    assert r.status_code == 403
    assert r.json()["detail"] == "pro_required"


@pytest.mark.asyncio
async def test_method_crud_and_encryption(db):
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/payment-methods",
            headers=seller_headers(),
            json={
                "kind": "card",
                "label": "Сбербанк",
                "account": "2202 2020 1111 2222",
                "holder": "Иван И.",
                "note": "в назначении номер заказа",
            },
        )
        assert r.status_code == 200, r.text
        method_id = r.json()["id"]
        assert r.json()["account"] == "2202 2020 1111 2222"

        r = await c.get(f"/api/seller/bots/{bot_id}/payment-methods", headers=seller_headers())
        assert [m["label"] for m in r.json()] == ["Сбербанк"]

        r = await c.put(
            f"/api/seller/bots/{bot_id}/payment-methods/{method_id}",
            headers=seller_headers(),
            json={"kind": "sbp", "label": "СБП", "account": "+79990001122", "is_active": False},
        )
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == "sbp"
        assert r.json()["is_active"] is False

    # в базе номер лежит шифрованным, а не текстом
    async with db() as session:
        method = await session.get(ShopPaymentMethod, method_id)
        assert b"79990001122" not in method.account_encrypted
        assert method.account == "+79990001122"

    async with client() as c:
        r = await c.delete(
            f"/api/seller/bots/{bot_id}/payment-methods/{method_id}", headers=seller_headers()
        )
        assert r.status_code == 200
        r = await c.get(f"/api/seller/bots/{bot_id}/payment-methods", headers=seller_headers())
        assert r.json() == []


@pytest.mark.asyncio
async def test_method_requires_label_and_account(db):
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/payment-methods",
            headers=seller_headers(),
            json={"kind": "card", "label": "  ", "account": "2202"},
        )
        assert r.status_code == 400
        r = await c.post(
            f"/api/seller/bots/{bot_id}/payment-methods",
            headers=seller_headers(),
            json={"kind": "gold", "label": "Банк", "account": "2202"},
        )
        assert r.status_code == 400


# --------------------------------------------------------------------------
# Витрина и чекаут
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_options_hidden_without_pro(db):
    bot_id = await setup_shop(db)
    await add_method(db, bot_id)
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
    # реквизиты заведены, но тариф кончился — перевода на чекауте нет
    assert r.json()["payment_options"] == []


@pytest.mark.asyncio
async def test_options_visible_with_pro_and_hide_disabled(db):
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    await add_method(db, bot_id, label="Сбербанк")
    await add_method(db, bot_id, label="Выключенный", is_active=False)
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
    options = r.json()["payment_options"]
    assert [o["label"] for o in options] == ["Сбербанк"]
    assert options[0]["account"] == "2202 2020 1111 2222"


@pytest.mark.asyncio
async def test_order_by_transfer_has_no_invoice_and_keeps_requisites(db):
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    method_id = await add_method(db, bot_id)
    async with client() as c:
        product_id = await add_product(c, bot_id)
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": product_id, "qty": 1}],
                "delivery": {"address": "Тверская 1"},
                "payment_method": "p2p",
                "payment_method_id": method_id,
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["payment_method"] == "p2p"
    assert body["payment_url"] is None  # счёт не выписывался
    assert body["payment_details"]["account"] == "2202 2020 1111 2222"
    assert body["paid_claimed_at"] is None


@pytest.mark.asyncio
async def test_requisites_survive_method_deletion(db):
    """Снимок, а не ссылка: продавец удалил способ — в заказе осталось то,
    куда покупателя реально просили перевести."""
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    method_id = await add_method(db, bot_id)
    async with client() as c:
        product_id = await add_product(c, bot_id)
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": product_id, "qty": 1}],
                "delivery": {"address": "Тверская 1"},
                "payment_method": "p2p",
                "payment_method_id": method_id,
            },
        )
        order_id = r.json()["id"]
        await c.delete(
            f"/api/seller/bots/{bot_id}/payment-methods/{method_id}", headers=seller_headers()
        )
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
    order = next(o for o in r.json() if o["id"] == order_id)
    assert order["payment_details"]["account"] == "2202 2020 1111 2222"


@pytest.mark.asyncio
async def test_transfer_refused_without_pro_or_method(db):
    bot_id = await setup_shop(db)
    method_id = await add_method(db, bot_id)
    async with client() as c:
        product_id = await add_product(c, bot_id)
        base = {
            "items": [{"product_id": product_id, "qty": 1}],
            "delivery": {"address": "Тверская 1"},
            "payment_method": "p2p",
        }
        # тарифа нет
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={**base, "payment_method_id": method_id},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "transfer_unavailable"

        await make_pro(db, bot_id)
        # чужой/несуществующий способ
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={**base, "payment_method_id": 99999},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "payment_method_not_found"


# --------------------------------------------------------------------------
# «Я оплатил» -> подтверждение продавцом
# --------------------------------------------------------------------------


async def make_transfer_order(db, c, bot_id: int, **product_kw) -> tuple[int, int]:
    """(order_id, product_id) заказа с оплатой переводом."""
    method_id = await add_method(db, bot_id)
    product_id = await add_product(c, bot_id, **product_kw)
    r = await c.post(
        f"/api/store/{bot_id}/orders",
        headers=buyer_headers(),
        json={
            "items": [{"product_id": product_id, "qty": 1}],
            "delivery": {"address": "Тверская 1"},
            "payment_method": "p2p",
            "payment_method_id": method_id,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"], product_id


@pytest.mark.asyncio
async def test_claim_does_not_pay_the_order(db):
    """«Я оплатил» — это заявка, а не оплата: платформа перевода не видела."""
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        order_id, _ = await make_transfer_order(db, c, bot_id)
        with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as push:
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/paid-claim", headers=buyer_headers()
            )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending_payment"
    assert r.json()["paid_claimed_at"] is not None
    # продавца позвали проверить поступление
    assert push.await_count == 1
    assert str(order_id) in push.await_args.args[1]

    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "pending_payment"
        assert order.paid_at is None


@pytest.mark.asyncio
async def test_confirmed_transfer_creates_no_payout(db):
    """Ядро решения: деньги пришли продавцу напрямую — платформе выплачивать
    нечего и комиссию брать не с чего."""
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        order_id, product_id = await make_transfer_order(db, c, bot_id)
        await c.post(f"/api/store/{bot_id}/orders/{order_id}/paid-claim", headers=buyer_headers())
        with patch("app.payments.service._notify", new=AsyncMock(return_value=True)), patch(
            "app.bots.hub.hub_bot.send_message", new=AsyncMock()
        ):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/confirm-payment",
                headers=seller_headers(),
            )
    assert r.status_code == 200, r.text

    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "paid"
        assert order.paid_at is not None
        payouts = (
            await session.execute(select(Payout).where(Payout.order_id == order_id))
        ).scalars().all()
        assert payouts == []
        # сток списан ровно один раз — путь тот же, что и у оплаты счётом
        from app.models import Product

        assert (await session.get(Product, product_id)).stock == 4


@pytest.mark.asyncio
async def test_crypto_order_still_creates_payout(db):
    """Обратная сторона: у обычного заказа выплата обязана остаться.
    Без этого теста рефакторинг «оплаты» тихо унёс бы кассу магазина."""
    from app.payments.service import handle_invoice_paid

    bot_id = await setup_shop(db)
    async with client() as c:
        product_id = await add_product(c, bot_id)
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": product_id, "qty": 1}],
                "delivery": {"address": "Тверская 1"},
            },
        )
        order_id = r.json()["id"]

    async with db() as session:
        order = await session.get(Order, order_id)
        order.invoice_id = 424242
        await session.commit()

    with patch("app.payments.service._notify", new=AsyncMock(return_value=True)), patch(
        "app.bots.hub.hub_bot.send_message", new=AsyncMock()
    ):
        assert await handle_invoice_paid(424242, f"order:{order_id}") is True

    async with db() as session:
        payout = (
            await session.execute(select(Payout).where(Payout.order_id == order_id))
        ).scalar_one()
        assert payout.amount > 0
        assert payout.commission > 0


@pytest.mark.asyncio
async def test_confirm_is_idempotent(db):
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        order_id, _ = await make_transfer_order(db, c, bot_id)
        with patch("app.payments.service._notify", new=AsyncMock(return_value=True)), patch(
            "app.bots.hub.hub_bot.send_message", new=AsyncMock()
        ):
            first = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/confirm-payment",
                headers=seller_headers(),
            )
            second = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/confirm-payment",
                headers=seller_headers(),
            )
    assert first.status_code == 200
    assert second.status_code == 409  # второе нажатие ничего не делает


@pytest.mark.asyncio
async def test_reject_returns_order_to_waiting(db):
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        order_id, _ = await make_transfer_order(db, c, bot_id)
        with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
            await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/paid-claim", headers=buyer_headers()
            )
        r = await c.post(
            f"/api/seller/bots/{bot_id}/orders/{order_id}/reject-payment",
            headers=seller_headers(),
        )
    assert r.status_code == 200, r.text

    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "pending_payment"
        assert order.paid_claimed_at is None
        assert order.expires_at is not None  # снова живёт по таймеру


@pytest.mark.asyncio
async def test_claimed_order_is_not_expired_by_the_job(db):
    """Покупатель сказал, что перевёл, — заказ снимается с автоотмены.
    Иначе деньги ушли бы в никуда по таймеру."""
    from datetime import datetime, timedelta, timezone

    from app.services.order_health import expire_unpaid_orders

    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        claimed_id, _ = await make_transfer_order(db, c, bot_id)
        quiet_id, _ = await make_transfer_order(db, c, bot_id)
        with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
            await c.post(
                f"/api/store/{bot_id}/orders/{claimed_id}/paid-claim", headers=buyer_headers()
            )

    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    async with db() as session:
        for oid in (claimed_id, quiet_id):
            (await session.get(Order, oid)).expires_at = past
        await session.commit()

    assert await expire_unpaid_orders() == 1

    async with db() as session:
        assert (await session.get(Order, claimed_id)).status == "pending_payment"
        assert (await session.get(Order, quiet_id)).status == "cancelled"


@pytest.mark.asyncio
async def test_chat_opens_before_payment_for_transfer_orders(db):
    """Про перевод и договариваются в чате — значит он открыт до оплаты.
    У обычного неоплаченного заказа чата по-прежнему нет."""
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        p2p_id, product_id = await make_transfer_order(db, c, bot_id)
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": product_id, "qty": 1}],
                "delivery": {"address": "Тверская 1"},
            },
        )
        crypto_id = r.json()["id"]

        r = await c.get(f"/api/store/{bot_id}/orders/{p2p_id}/chat", headers=buyer_headers())
        assert r.status_code == 200, r.text
        assert r.json()["can_send"] is True

        r = await c.get(f"/api/store/{bot_id}/orders/{crypto_id}/chat", headers=buyer_headers())
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_transfer_order_has_no_crypto_invoice_route(db):
    """У p2p-заказа не должно быть второй дороги к оплате: счёт в Crypto Pay
    по нему не выписывается даже кнопкой «Оплатить»."""
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        order_id, _ = await make_transfer_order(db, c, bot_id)
        r = await c.post(f"/api/store/{bot_id}/orders/{order_id}/pay", headers=buyer_headers())
    assert r.status_code == 400
    assert r.json()["detail"] == "order is paid by transfer"


@pytest.mark.asyncio
async def test_seller_sees_claimed_transfer_but_not_abandoned_cart(db):
    """Подтвердить перевод может только продавец — значит он обязан увидеть
    такой заказ, хотя формально тот ещё не оплачен. Брошенные корзины при
    этом в список не лезут."""
    bot_id = await setup_shop(db)
    await make_pro(db, bot_id)
    async with client() as c:
        claimed_id, _ = await make_transfer_order(db, c, bot_id)
        quiet_id, _ = await make_transfer_order(db, c, bot_id)
        with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
            await c.post(
                f"/api/store/{bot_id}/orders/{claimed_id}/paid-claim", headers=buyer_headers()
            )
        r = await c.get(f"/api/seller/bots/{bot_id}/orders", headers=seller_headers())

    ids = {o["id"] for o in r.json()}
    assert claimed_id in ids
    assert quiet_id not in ids
    row = next(o for o in r.json() if o["id"] == claimed_id)
    assert row["payment_method"] == "p2p"
    assert row["paid_claimed_at"] is not None
