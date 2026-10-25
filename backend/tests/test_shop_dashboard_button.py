"""Кнопка «Кабинет магазина» на /start seller-бота и вход в кабинет по
подписи самого магазина (X-Bot-Id) — только для владельца."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.handlers.hub import newshop
from app.handlers.seller import start as seller_start
from app.models import Seller, SellerBot
from app.security import encrypt_bot_token
from tests.test_api import (
    SELLER_BOT_TOKEN,
    SELLER_TG,
    client,
    init_data_for,
    seller_headers,
    setup_shop,
)
from tests.test_bot_settings import load_bot
from tests.test_hub_menus import FAKE_SETTINGS

VICTIM_TG = {"id": 222, "first_name": "Чужой", "username": "victim"}
VICTIM_TOKEN = "444555666:AAvictim-seller-bot-token-for-tests"


async def _victim_shop(db) -> int:
    async with db() as session:
        seller = Seller(telegram_id=VICTIM_TG["id"])
        session.add(seller)
        await session.flush()
        bot = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=encrypt_bot_token(VICTIM_TOKEN),
            bot_username="victim_shop_bot",
            telegram_bot_id=444555666,
        )
        session.add(bot)
        await session.commit()
        return bot.id


def shop_signed(user: dict, bot_id: int, token: str = SELLER_BOT_TOKEN) -> dict:
    return {"X-Init-Data": init_data_for(user, token), "X-Bot-Id": str(bot_id)}


# --------------------------------------------------------------------------
# Авторизация кабинета подписью магазина
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_opens_dashboard_from_own_bot(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.get(f"/api/seller/bots/{bot_id}/channels", headers=shop_signed(SELLER_TG, bot_id))
        assert r.status_code == 200
        # список магазинов тоже: после перехода «назад» в /shops
        r = await c.get("/api/seller/me", headers=shop_signed(SELLER_TG, bot_id))
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_shop_token_cannot_impersonate_another_seller(db):
    """Свой токен бота продавец знает и может подписать initData с чужим id.
    Такую подпись принимаем только за владельца этого бота."""
    bot_id = await setup_shop(db)
    victim_bot = await _victim_shop(db)
    forged = shop_signed(VICTIM_TG, bot_id)
    async with client() as c:
        assert (await c.get("/api/seller/me", headers=forged)).status_code == 401
        r = await c.get(f"/api/seller/bots/{victim_bot}/channels", headers=forged)
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_shop_signed_init_data_needs_matching_bot(db):
    bot_id = await setup_shop(db)
    victim_bot = await _victim_shop(db)
    async with client() as c:
        # подпись токеном одного магазина, а заголовок — другого
        r = await c.get("/api/seller/me", headers=shop_signed(SELLER_TG, victim_bot))
        assert r.status_code == 401
        # без заголовка подпись магазина не принимается вовсе
        r = await c.get("/api/seller/me", headers={"X-Init-Data": init_data_for(SELLER_TG, SELLER_BOT_TOKEN)})
        assert r.status_code == 401
        for junk in ("abc", "99999999999999", "-1"):
            r = await c.get("/api/seller/me", headers=shop_signed(SELLER_TG, junk))
            assert r.status_code == 401


@pytest.mark.asyncio
async def test_hub_signed_init_data_still_works(db):
    bot_id = await setup_shop(db)
    headers = {**seller_headers(), "X-Bot-Id": str(bot_id)}
    async with client() as c:
        assert (await c.get("/api/seller/me", headers=headers)).status_code == 200


# --------------------------------------------------------------------------
# Кнопка на /start
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_sees_dashboard_button_buyer_does_not(db):
    bot_id = await setup_shop(db)
    bot = await load_bot(db, bot_id)
    with patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS):
        owner_kb = await seller_start.start_keyboard(bot, None, SimpleNamespace(id=SELLER_TG["id"]))
        buyer_kb = await seller_start.start_keyboard(bot, None, SimpleNamespace(id=999))

    first = owner_kb.inline_keyboard[0][0]
    assert first.text == "🛠 Кабинет магазина"
    assert first.web_app.url == f"https://app.example.com/shop/{bot_id}"
    # витрина у владельца на месте — второй строкой
    assert owner_kb.inline_keyboard[1][0].web_app.url.endswith(f"?bot_id={bot_id}")

    labels = [b.text for row in buyer_kb.inline_keyboard for b in row]
    assert "🛠 Кабинет магазина" not in labels


# --------------------------------------------------------------------------
# После создания бота
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creator_welcome_comes_from_the_new_bot(db):
    """Первый /start в новом боте часто теряется — приветствие с кабинетом
    шлёт сам seller-бот."""
    bot_id = await setup_shop(db)
    bot = await load_bot(db, bot_id)
    fake = SimpleNamespace(send_message=AsyncMock(), session=SimpleNamespace(close=AsyncMock()))
    with (
        patch("app.bots.runner.make_seller_bot", return_value=fake),
        patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS),
    ):
        await newshop.welcome_creator_from_bot(bot, SimpleNamespace(id=SELLER_TG["id"]))

    args = fake.send_message.await_args
    assert args.args[0] == SELLER_TG["id"]
    kb = args.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].text == "🛠 Кабинет магазина"
    fake.session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_creator_welcome_failure_is_quiet(db):
    bot_id = await setup_shop(db)
    bot = await load_bot(db, bot_id)
    fake = SimpleNamespace(
        send_message=AsyncMock(side_effect=RuntimeError("Forbidden")),
        session=SimpleNamespace(close=AsyncMock()),
    )
    with patch("app.bots.runner.make_seller_bot", return_value=fake):
        await newshop.welcome_creator_from_bot(bot, SimpleNamespace(id=SELLER_TG["id"]))
    fake.session.close.assert_awaited_once()
