"""Готовность @CryptoBot больше не спрашивается у продавца — она выясняется
самим переводом.

Раньше вывод был закрыт guard'ом `payment_not_connected`, а снимала его кнопка
«Готово, я нажал /start»: продавец подтверждал сам за себя, и ошибиться в обе
стороны было одинаково легко. Crypto Pay проверить это не умеет (в API нет
такого метода), поэтому единственный честный источник правды — результат
transfer. Эти тесты фиксируют новое поведение.
"""

import os
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models import Seller, SellerBot
from app.security import encrypt_bot_token
from tests.test_payments import make_order, patched_notifications

SELLER_BOT_TOKEN = "111222333:AAtest-seller-bot-token-for-api-tests"
SELLER_TG = {"id": 5151, "first_name": "Продавец", "username": "prereq_seller"}


def init_data_for(user: dict) -> str:
    from app.services.webapp_auth import sign_init_data

    return sign_init_data({"auth_date": int(time.time()), "user": user}, os.environ["HUB_BOT_TOKEN"])


def client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def seller_headers() -> dict:
    return {"X-Init-Data": init_data_for(SELLER_TG)}


async def setup_shop(db) -> int:
    """Продавец, который ни разу не открывал @CryptoBot. Возвращает bot_id."""
    async with db() as session:
        seller = Seller(telegram_id=SELLER_TG["id"])
        session.add(seller)
        await session.flush()
        bot = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=encrypt_bot_token(SELLER_BOT_TOKEN),
            bot_username="prereq_bot",
            telegram_bot_id=111222333,
        )
        session.add(bot)
        await session.commit()
        return bot.id


@pytest.mark.asyncio
async def test_withdraw_is_not_blocked_by_unconfirmed_cryptobot(db):
    """Вывод доходит до проверки баланса, а не упирается в подтверждение оплаты."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["reason"] == "no_funds"


@pytest.mark.asyncio
async def test_self_attestation_endpoint_is_gone(db):
    """Кнопки «Готово, я нажал /start» нет — вместе с ней ушёл и эндпоинт."""
    await setup_shop(db)
    async with client() as c:
        r = await c.post("/api/seller/onboarding/payment-done", headers=seller_headers())
        # 405, а не 404: путь ловит SPA-fallback, но уже только на GET
        assert r.status_code in (404, 405)


async def _shop_with_funds(db) -> int:
    """Магазин с накопленной выплатой и продавцом без отметки о @CryptoBot."""
    await make_order(db, product_type="physical", digital_url=None, total=Decimal("100"))
    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)

    async with db() as session:
        shop = (await session.execute(select(SellerBot))).scalars().first()
        seller = await session.get(Seller, shop.seller_id)
        seller.cryptobot_connected = False
        await session.commit()
        return shop.id


@pytest.mark.asyncio
async def test_transfer_to_closed_cryptobot_reports_actionable_reason(db):
    """USER_NOT_FOUND — единственный отказ, который продавец чинит сам."""
    bot_id = await _shop_with_funds(db)
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(side_effect=Exception("CodeErrorFactory_400: [400] USER_NOT_FOUND"))
    )
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        result = await flush_shop_payouts(bot_id)

    assert result.ok is False
    assert result.reason == "cryptobot_not_started"

    async with db() as session:
        shop = await session.get(SellerBot, bot_id)
        seller = await session.get(Seller, shop.seller_id)
        # неудачный перевод ничего не «подтверждает»
        assert seller.cryptobot_connected is False


@pytest.mark.asyncio
async def test_successful_transfer_marks_cryptobot_connected(db):
    """Состоявшийся перевод — доказательство, что @CryptoBot открыт."""
    bot_id = await _shop_with_funds(db)
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(return_value=SimpleNamespace(transfer_id=4242))
    )
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        result = await flush_shop_payouts(bot_id)

    assert result.ok is True
    assert result.reason is None

    async with db() as session:
        shop = await session.get(SellerBot, bot_id)
        seller = await session.get(Seller, shop.seller_id)
        assert seller.cryptobot_connected is True


@pytest.mark.asyncio
async def test_other_transfer_errors_stay_generic(db):
    """Прочие отказы не выдаются за «не нажат Start» — шаг с @CryptoBot не покажется."""
    bot_id = await _shop_with_funds(db)
    from app.payments.payouts import flush_shop_payouts

    fake_crypto = SimpleNamespace(
        transfer=AsyncMock(side_effect=Exception("CodeErrorFactory_400: [400] NOT_ENOUGH_COINS"))
    )
    with (
        patch("app.payments.payouts.get_crypto_pay", return_value=fake_crypto),
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()),
    ):
        result = await flush_shop_payouts(bot_id)

    assert result.ok is False
    assert result.reason == "failed"
