"""Канал «Связаться с нами»: обращения покупателей и продавцов платформе.

Пуш уходит от hub-бота всем админам из ADMIN_TELEGRAM_IDS с контекстом
(кто, из какого магазина, экран, версия). Копии в БД нет — история живёт
в Telegram, поэтому проверяем именно содержимое пуша.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Seller, SellerBot
from app.services.feedback import reset_rate_limit
from tests.test_api import (
    BUYER,
    SELLER_TG,
    buyer_headers,
    client,
    init_data_for,
    seller_headers,
    setup_shop,
)

ADMIN_TG_ID = 555000


@pytest.fixture(autouse=True)
def _clean_rate_window():
    """Окно rate-limit module-level: без сброса соседний тест ловил бы 429
    за обращения предыдущего."""
    reset_rate_limit()
    yield
    reset_rate_limit()


@pytest.fixture
def admins():
    """Админ платформы в окружении. get_settings закэширован — без
    cache_clear эндпоинт увидел бы старых (пустых) админов."""
    os.environ["ADMIN_TELEGRAM_IDS"] = str(ADMIN_TG_ID)
    get_settings.cache_clear()
    yield
    os.environ.pop("ADMIN_TELEGRAM_IDS", None)
    get_settings.cache_clear()


def feedback_payload(**kw) -> dict:
    payload = {
        "type": "bug",
        "message": "Не открывается корзина",
        "screen": "/profile",
        "app_version": "0.1.0",
    }
    payload.update(kw)
    return payload


@pytest.mark.asyncio
async def test_buyer_feedback_reaches_admin_with_context(db, admins):
    bot_id = await setup_shop(db)
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        async with client() as c:
            r = await c.post(
                f"/api/store/{bot_id}/feedback",
                headers=buyer_headers(),
                json=feedback_payload(message="<b>жирный</b> текст"),
            )
        assert r.status_code == 200, r.text
        assert r.json() == {"status": "sent"}

        send.assert_awaited_once()
        admin_id, text = send.await_args.args
        assert admin_id == ADMIN_TG_ID
        # тип, чей фидбек и кто отправитель
        assert "🐛 Проблема" in text
        assert "от покупателя" in text
        assert f"ID {BUYER['id']}" in text
        # магазин и экран/версия
        assert "@petshop_bot" in text
        assert f"bot_id {bot_id}" in text
        assert "/profile" in text
        assert "0.1.0" in text
        # метка времени на месте; текст экранирован, а не исполнен (HTML-пуш)
        assert "UTC" in text
        assert "&lt;b&gt;жирный&lt;/b&gt;" in text
        assert "<b>" not in text


@pytest.mark.asyncio
async def test_feedback_disabled_without_admins(db):
    """Некому доставлять — форма не должна молча глотать обращения."""
    os.environ.pop("ADMIN_TELEGRAM_IDS", None)
    get_settings.cache_clear()
    bot_id = await setup_shop(db)
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        async with client() as c:
            r = await c.post(
                f"/api/store/{bot_id}/feedback",
                headers=buyer_headers(),
                json=feedback_payload(),
            )
        assert r.status_code == 503
        send.assert_not_awaited()


@pytest.mark.asyncio
async def test_telegram_failure_is_502(db, admins):
    bot_id = await setup_shop(db)
    with patch(
        "app.bots.hub.hub_bot.send_message", new=AsyncMock(side_effect=Exception("tg down"))
    ):
        async with client() as c:
            r = await c.post(
                f"/api/store/{bot_id}/feedback",
                headers=buyer_headers(),
                json=feedback_payload(),
            )
        assert r.status_code == 502


@pytest.mark.asyncio
async def test_disabled_shop_still_accepts_feedback(db, admins):
    """Магазин выключен, а деньги покупателя у продавца: именно такие и пишут
    в поддержку. Тот же принцип, что у «своих заказов» (get_buyer_any_shop)."""
    bot_id = await setup_shop(db)
    async with db() as session:
        shop = await session.get(SellerBot, bot_id)
        shop.is_active = False
        await session.commit()

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
        async with client() as c:
            r = await c.post(
                f"/api/store/{bot_id}/feedback",
                headers=buyer_headers(),
                json=feedback_payload(),
            )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_fifth_message_passes_sixth_is_rate_limited(db, admins):
    bot_id = await setup_shop(db)
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
        async with client() as c:
            for _ in range(5):
                r = await c.post(
                    f"/api/store/{bot_id}/feedback",
                    headers=buyer_headers(),
                    json=feedback_payload(),
                )
                assert r.status_code == 200, r.text
            r = await c.post(
                f"/api/store/{bot_id}/feedback",
                headers=buyer_headers(),
                json=feedback_payload(),
            )
        assert r.status_code == 429


@pytest.mark.asyncio
async def test_unknown_type_is_rejected(db, admins):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/store/{bot_id}/feedback",
            headers=buyer_headers(),
            json=feedback_payload(type="spam"),
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_seller_feedback_reaches_admin_with_context(db, admins):
    bot_id = await setup_shop(db)
    # setup_shop создаёт продавца голым telegram_id: имя и username попадают
    # в sellers при /start, здесь проставляем их руками
    async with db() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == SELLER_TG["id"]))
        ).scalar_one()
        seller.first_name = SELLER_TG["first_name"]
        seller.username = SELLER_TG["username"]
        await session.commit()

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/feedback",
                headers=seller_headers(),
                json=feedback_payload(type="idea", message="Добавьте promocodes"),
            )
        assert r.status_code == 200, r.text
        assert r.json() == {"status": "sent"}

        send.assert_awaited_once()
        admin_id, text = send.await_args.args
        assert admin_id == ADMIN_TG_ID
        assert "💡 Идея" in text
        assert "от продавца" in text
        assert f"ID {SELLER_TG['id']}" in text
        assert "@seller1" in text
        assert f"bot_id {bot_id}" in text


@pytest.mark.asyncio
async def test_stranger_cannot_send_feedback_as_someones_shop(db, admins):
    """Чужой продавец получает ту же 404, что и несуществующий магазин:
    сам факт существования магазина посторонним раскрывать не нужно."""
    bot_id = await setup_shop(db)
    async with db() as session:
        session.add(Seller(telegram_id=222, first_name="Чужак", username="stranger"))
        await session.commit()

    stranger = {"id": 222, "first_name": "Чужак", "username": "stranger"}
    stranger_headers = {
        "X-Init-Data": init_data_for(stranger, os.environ["HUB_BOT_TOKEN"])
    }
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/feedback",
                headers=stranger_headers,
                json=feedback_payload(),
            )
        assert r.status_code == 404
        send.assert_not_awaited()


@pytest.mark.asyncio
async def test_feedback_enabled_flag_follows_admins(db, admins):
    """Флагом в ответах фронт решает, рисовать ли пункт «Связаться с нами»:
    без админов кнопка скрыта — как раньше пряталась ссылка поддержки."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert r.json()["feedback_enabled"] is True
        r = await c.get("/api/seller/me", headers=seller_headers())
        assert r.json()["feedback_enabled"] is True

    os.environ.pop("ADMIN_TELEGRAM_IDS", None)
    get_settings.cache_clear()
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert r.json()["feedback_enabled"] is False
        r = await c.get("/api/seller/me", headers=seller_headers())
        assert r.json()["feedback_enabled"] is False
