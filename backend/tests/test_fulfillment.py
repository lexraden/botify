from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Payout, PayoutBatch, SellerBot
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
async def test_flush_shop_payouts_success_without_double_transfer(db):
    await make_order(db, product_type="physical", digital_url=None)
    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)

    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=31337))
    )
    with patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto):
        assert (await flush_shop_payouts(bot_id)).ok is True
        # повторное нажатие «Вывести» не делает второй transfer — выводить нечего
        assert (await flush_shop_payouts(bot_id)).ok is False
    assert fake_crypto.transfer.await_count == 1
    assert fake_crypto.transfer.call_args.kwargs["amount"] == pytest.approx(95.0)

    async with db() as session:
        batch = (await session.execute(select(PayoutBatch))).scalar_one()
        payout = (await session.execute(select(Payout))).scalar_one()
        # уходит сохранённый в пачке случайный токен, а не её порядковый id
        assert fake_crypto.transfer.call_args.kwargs["spend_id"] == batch.spend_id
        assert payout.status == "sent"
        assert payout.transfer_id == 31337


@pytest.mark.asyncio
async def test_transfer_sends_stored_random_spend_token(db):
    """spend_id берётся из пачки (случайный токен), а не из её порядкового id:
    после сброса базы нумерация id начинается заново, и batch-{id} столкнулся
    бы с уже использованным spend_id в Crypto Pay."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))
    await _paid_order_payout(db)
    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=909))
    )
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        assert (await flush_shop_payouts(bot_id)).ok is True

    async with db() as session:
        batch = (await session.execute(select(PayoutBatch))).scalar_one()
        # следующая пачка получает свой случайный токен, не совпадающий с чужим
        other = PayoutBatch(seller_id=batch.seller_id, bot_id=batch.bot_id, amount=Decimal("3"))
        session.add(other)
        await session.commit()
        assert other.spend_id != batch.spend_id

    sent = fake_crypto.transfer.call_args.kwargs["spend_id"]
    assert sent == batch.spend_id  # шлём ровно то, что храним в пачке
    assert sent != f"batch-{batch.id}"


@pytest.mark.asyncio
async def test_paid_order_does_not_transfer_by_itself(db):
    """Авто-выплат нет: оплата кладёт деньги в кассу магазина и ждёт продавца."""
    auto = SimpleNamespace(transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=1)))
    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=auto),
        p1,
        p2,
    ):
        # полностью digital-заказ: раньше именно он запускал выплату сразу
        await make_order(db)
        await handle_invoice_paid(555001, None)

    auto.transfer.assert_not_called()
    async with db() as session:
        batches = (await session.execute(select(PayoutBatch))).scalars().all()
        assert batches == []  # пачку никто не собирал
        payout = (await session.execute(select(Payout))).scalar_one()
        assert payout.status == "pending"


@pytest.mark.asyncio
async def test_flush_failure_marks_failed_and_notifies(db):
    await make_order(db, product_type="physical", digital_url=None)
    p1, p2 = patched_notifications()
    with p1, p2:
        from app.payments.service import handle_invoice_paid

        await handle_invoice_paid(555001, None)

    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(transfer=AsyncMock(side_effect=Exception("USER_NOT_FOUND")))
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        assert (await flush_shop_payouts(bot_id)).ok is False

    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        assert payout.status == "failed"
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
    await _paid_order_payout(db)

    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(transfer=AsyncMock())
    with (
        _settings_with(min_payout_usdt=10.0),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        assert (await flush_shop_payouts(bot_id)).ok is False

    assert fake_crypto.transfer.await_count == 0  # заведомо провальный transfer не делаем
    assert hub_mock.await_count == 0  # и продавца не тревожим
    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        assert payout.status == "pending" and payout.batch_id is None


@pytest.mark.asyncio
async def test_payouts_of_several_orders_go_in_one_transfer(db):
    """Накопленное уходит одним переводом на всю сумму."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("1"))
    await _paid_order_payout(db)
    await make_order(
        db, product_type="physical", digital_url=None, total=Decimal("1"), invoice_id=555002
    )

    from app.payments.payouts import flush_shop_payouts

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
            bot_id = (await session.execute(select(SellerBot))).scalars().first().id
        assert (await flush_shop_payouts(bot_id)).ok is True

    assert fake_crypto.transfer.await_count == 1
    assert fake_crypto.transfer.call_args.kwargs["amount"] == pytest.approx(1.90)  # 2 × 0.95
    assert "1.90" in hub_mock.call_args.args[1]

    async with db() as session:
        payouts = (await session.execute(select(Payout))).scalars().all()
        assert {p.status for p in payouts} == {"sent"}
        assert {p.transfer_id for p in payouts} == {4242}


@pytest.mark.asyncio
async def test_amount_too_small_releases_batch_for_later(db):
    """Если минимум Crypto Pay выше нашего — пачка распускается, деньги копятся."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("1"))
    await _paid_order_payout(db)

    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(side_effect=Exception("CodeErrorFactory_400: [400] AMOUNT_TOO_SMALL"))
    )
    with (
        _settings_with(min_payout_usdt=0.5),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        assert (await flush_shop_payouts(bot_id)).ok is False

    assert hub_mock.await_count == 0  # продавцу это знать незачем
    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        assert payout.status == "pending"  # не failed: следующее «Вывести» соберёт заново
        assert payout.batch_id is None  # пачка распущена, сумма растёт дальше
        batch = (await session.execute(select(PayoutBatch))).scalar_one()
        assert batch.status == "too_small" and "AMOUNT_TOO_SMALL" in batch.last_error


@pytest.mark.asyncio
async def test_provider_fee_is_paid_by_the_platform(db):
    """С продавца берём только наши 5%; комиссию сервиса платим из них."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))

    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        # Crypto Pay сообщил, что удержал 3 USDT со стодолларового платежа
        await handle_invoice_paid(555001, None, fee_amount=Decimal("3"))

    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        assert Decimal(payout.commission) == Decimal("5.000000")
        assert Decimal(payout.amount) == Decimal("95.000000")      # 100 − 5, и только
        # комиссия сервиса записана, но долю продавца не трогает: маржа 5 − 3 = 2
        assert Decimal(payout.provider_fee) == Decimal("3.000000")


@pytest.mark.asyncio
async def test_provider_fee_falls_back_to_configured_rate(db):
    """Если вебхук не прислал комиссию сервиса — оцениваем её по ставке."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))

    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)

    async with db() as session:
        payout = (await session.execute(select(Payout))).scalar_one()
        assert Decimal(payout.provider_fee) == Decimal("3.000000")  # 3% по умолчанию
        assert Decimal(payout.amount) == Decimal("95.000000")  # на выплату не влияет


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

    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id

    # 1 USDT − 5% = 0.95, до минимума в 2 USDT не хватает
    async with client() as c:
        r = await c.post(f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers())
        body = r.json()
    assert body["ok"] is False and body["reason"] == "below_min"
    assert float(body["pending"]) == pytest.approx(0.95)

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
    # эндпоинт проверяет наличие клиента отдельно от payouts.py, поэтому
    # подменяем оба места: иначе кнопка честно ответит «оплата не настроена»
    with (
        patch("app.payments.client.get_crypto_pay", return_value=fake_crypto),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers()
            )
            body = r.json()

    assert body["ok"] is True
    assert float(body["sent"]) == pytest.approx(5.70)  # 0.95 + 4.75
    assert float(body["pending"]) == 0
    assert fake_crypto.transfer.await_count == 1

    # повторное нажатие уже ничего не отправляет
    with (
        patch("app.payments.client.get_crypto_pay", return_value=fake_crypto),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
    ):
        async with client() as c:
            r = await c.post(f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers())
    assert r.json()["reason"] == "no_funds"
    assert fake_crypto.transfer.await_count == 1


@pytest.mark.asyncio
async def test_each_shop_has_its_own_till(db):
    """У двух ботов одного продавца кассы раздельные и не смешиваются."""
    from app.payments.payouts import flush_shop_payouts, pending_total
    from app.security import encrypt_bot_token

    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))
    await _paid_order_payout(db)  # выплата 95 в первом магазине

    async with db() as session:
        shop_a = (await session.execute(select(SellerBot))).scalars().first()
        shop_b = SellerBot(
            seller_id=shop_a.seller_id,
            bot_token_encrypted=encrypt_bot_token("222:second-shop-token-aaaaaaaaaaaaaaaa"),
            bot_username="second_shop_bot",
            telegram_bot_id=222333444,
        )
        session.add(shop_b)
        await session.commit()
        a_id, b_id = shop_a.id, shop_b.id

    async with db() as session:
        assert await pending_total(session, a_id) == Decimal("95.000000")
        assert await pending_total(session, b_id) == Decimal("0")  # чужие деньги не видны

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=7001))
    )
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock,
    ):
        # во втором магазине выводить нечего — перевода нет
        assert (await flush_shop_payouts(b_id)).ok is False
        assert fake_crypto.transfer.await_count == 0
        # в первом — уходит только его сумма
        assert (await flush_shop_payouts(a_id)).ok is True

    assert fake_crypto.transfer.call_args.kwargs["amount"] == pytest.approx(95.0)
    # в уведомлении названо, по какому именно магазину пришли деньги
    assert "@shop_bot" in hub_mock.call_args.args[1]


@pytest.mark.asyncio
async def test_summary_splits_balance_and_paid_out(db):
    """Кабинет различает баланс (ещё у нас) и выплаченное (уже у продавца)."""
    from tests.test_api import client, seller_headers

    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))
    await _paid_order_payout(db)

    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id

    async with client() as c:
        summary = (
            await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        ).json()
    assert float(summary["payout_pending"]) == pytest.approx(95.0)  # баланс
    assert float(summary["payout_paid"]) == 0  # ещё ничего не уходило

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=8100))
    )
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        from app.payments.payouts import flush_shop_payouts

        assert (await flush_shop_payouts(bot_id)).ok is True

    async with client() as c:
        summary = (
            await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        ).json()
    # деньги переехали из баланса в выплаченное, «всего заработано» не изменилось
    assert float(summary["payout_pending"]) == 0
    assert float(summary["payout_paid"]) == pytest.approx(95.0)


@pytest.mark.asyncio
async def test_platform_margin_is_commission_minus_provider_fee(db):
    """Маржа платформы: наши 5% минус то, что забрал Crypto Pay."""
    from app.payments.service import handle_invoice_paid
    from app.payments.stats import platform_margin

    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))
    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None, fee_amount=Decimal("2.9"))

    async with db() as session:
        margin = await platform_margin(session)

    assert margin.commission == Decimal("5.000000")
    assert margin.provider_fee == Decimal("2.900000")
    assert margin.net == Decimal("2.100000")  # столько реально осталось
    assert margin.volume_30d == Decimal("100.000000")

    # до первого порога скидки (10 000) не хватает оборота
    left, rate = margin.next_tier
    assert left == Decimal("9900.000000") and rate == Decimal("2.9")


def test_fee_tier_hint_stops_at_the_cheapest_rate():
    """Оборот выше верхнего порога — дальше снижать нечего."""
    from app.payments.stats import _next_tier

    assert _next_tier(Decimal(0)) == (Decimal(10_000), Decimal("2.9"))
    assert _next_tier(Decimal(30_000)) == (Decimal(20_000), Decimal("2.7"))
    assert _next_tier(Decimal(100_000)) is None


@pytest.mark.asyncio
async def test_failed_batch_is_retried_with_the_same_spend_id(db):
    """Упавший перевод повторяется той же пачкой — Crypto Pay не заплатит дважды."""
    from app.payments.payouts import flush_shop_payouts

    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))
    await _paid_order_payout(db)
    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id

    # первая попытка обрывается уже после того, как Crypto Pay мог принять перевод
    failing = SimpleNamespace(transfer=AsyncMock(side_effect=Exception("ReadTimeout")))
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=failing),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        assert (await flush_shop_payouts(bot_id)).ok is False

    async with db() as session:
        batch = (await session.execute(select(PayoutBatch))).scalar_one()
        assert batch.status == "failed" and "ReadTimeout" in batch.last_error

    retry = SimpleNamespace(transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=606)))
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=retry),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        assert (await flush_shop_payouts(bot_id)).ok is True

    # тот же spend_id и та же пачка: повторной выплаты по этим деньгам не будет
    assert (
        retry.transfer.call_args.kwargs["spend_id"]
        == failing.transfer.call_args.kwargs["spend_id"]
    )
    async with db() as session:
        batches = (await session.execute(select(PayoutBatch))).scalars().all()
        assert len(batches) == 1 and batches[0].status == "sent"
        payout = (await session.execute(select(Payout))).scalar_one()
        assert payout.status == "sent" and payout.transfer_id == 606


@pytest.mark.asyncio
async def test_withdraw_twice_in_a_row_sends_one_transfer(db):
    """Два нажатия «Вывести» подряд: перевод один, второй раз выводить нечего."""
    from tests.test_api import client, seller_headers

    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))
    await _paid_order_payout(db)
    async with db() as session:
        bot_id = (await session.execute(select(SellerBot))).scalars().first().id

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=707))
    )
    with (
        patch("app.payments.client.get_crypto_pay", return_value=fake_crypto),
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        async with client() as c:
            first = (
                await c.post(
                    f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers()
                )
            ).json()
            second = (
                await c.post(
                    f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers()
                )
            ).json()

    assert first["ok"] is True and float(first["sent"]) == pytest.approx(95.0)
    assert second["ok"] is False and second["reason"] == "no_funds"
    assert fake_crypto.transfer.await_count == 1
