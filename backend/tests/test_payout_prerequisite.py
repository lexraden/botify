import os
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.models import Seller, SellerBot
from app.security import encrypt_bot_token

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
    """Продавец без подключённой оплаты и его бот. Возвращает bot_id."""
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
async def test_withdraw_requires_connected_payment(db):
    """Оплата — prerequisite вывода: без @CryptoBot перевод не запускается."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["reason"] == "payment_not_connected"


@pytest.mark.asyncio
async def test_withdraw_after_payment_connection_reaches_balance_check(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        # подключение оплаты через существующий эндпоинт онбординга
        r = await c.post("/api/seller/onboarding/payment-done", headers=seller_headers())
        assert r.status_code == 200, r.text
        assert r.json()["cryptobot_connected"] is True

        r = await c.post(f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=seller_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        # guard пройден; упёрлись в пустой баланс, а не в отсутствие оплаты
        assert body["reason"] == "no_funds"
