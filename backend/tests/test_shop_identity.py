"""Идентичность магазина в шапке витрины: показное имя и логотип.

Дефолт имени — Telegram-имя бота из getMe при подключении; продавец меняет
имя и загружает лого из кабинета; витрина отдаёт имя, лого и trust-строку
(рейтинг по отзывам, число оплаченных продаж).
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import SellerBot, ShopLogo
from app.services.bot_connect import connect_seller_bot
from app.services.images import MAX_IMAGE_BYTES
from tests.test_api import (
    buyer_headers,
    client,
    init_data_for,
    seller_headers,
    setup_shop,
)
from tests.test_bot_connect import VALID_TOKEN, make_seller
from tests.test_product_images import JPEG_BYTES, PNG_BYTES


def mock_get_me_with_name(first_name="Shopik"):
    return patch(
        "app.services.bot_connect.Bot.get_me",
        new=AsyncMock(
            return_value=SimpleNamespace(
                id=987654321, username="test_shop_bot", first_name=first_name
            )
        ),
    )


def stranger_headers():
    return {
        "X-Init-Data": init_data_for({"id": 222}, os.environ["HUB_BOT_TOKEN"])
    }


# --- дефолт имени из Telegram -------------------------------------------


@pytest.mark.asyncio
async def test_connect_saves_first_name_as_shop_name(db):
    seller_id = await make_seller(db)
    with mock_get_me_with_name("Shopik"):
        result = await connect_seller_bot(seller_id, VALID_TOKEN)

    assert result.ok
    assert result.bot_record.shop_name == "Shopik"


@pytest.mark.asyncio
async def test_reconnect_fills_empty_shop_name_but_keeps_custom(db):
    """Реконнект дописывает дефолт ботам без имени и не затирает кастомное."""
    seller_id = await make_seller(db)
    async with db() as session:
        session.add(
            SellerBot(
                seller_id=seller_id,
                bot_username="test_shop_bot",
                telegram_bot_id=987654321,
                is_active=False,  # отключённый — путь переподключения
            )
        )
        await session.commit()

    with mock_get_me_with_name("Shopik"):
        first = await connect_seller_bot(seller_id, VALID_TOKEN)
    assert first.ok and first.bot_record.shop_name == "Shopik"

    async with db() as session:
        bot = await session.get(SellerBot, first.bot_record.id)
        bot.shop_name = "Кастомное имя"
        bot.is_active = False  # снова выключаем ради второго реконнекта
        await session.commit()

    with mock_get_me_with_name("Другое имя бота"):
        second = await connect_seller_bot(seller_id, VALID_TOKEN)
    assert second.ok and second.bot_record.shop_name == "Кастомное имя"


# --- PUT shop-name -------------------------------------------------------


@pytest.mark.asyncio
async def test_put_shop_name_sets_resets_and_guards(db):
    bot_id = await setup_shop(db)

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
        async with client() as c:
            # установка с обрезкой пробелов
            r = await c.put(
                f"/api/seller/bots/{bot_id}/shop-name",
                headers=seller_headers(),
                json={"shop_name": "  Кофейня у дома  "},
            )
            assert r.status_code == 200, r.text
            assert r.json()["shop_name"] == "Кофейня у дома"

            # витрина показывает заданное имя
            store = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
            assert store.json()["shop_name"] == "Кофейня у дома"

            # сброс null -> дефолт (@username ORM-бота без имени)
            r = await c.put(
                f"/api/seller/bots/{bot_id}/shop-name",
                headers=seller_headers(),
                json={"shop_name": None},
            )
            assert r.status_code == 200, r.text
            assert r.json()["shop_name"] is None
            store = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
            assert store.json()["shop_name"] == "@petshop_bot"

            # пустая строка — ошибка, а не молчаливый сброс
            r = await c.put(
                f"/api/seller/bots/{bot_id}/shop-name",
                headers=seller_headers(),
                json={"shop_name": "   "},
            )
            assert r.status_code == 422

            # длиннее 64 символов pydantic не пропустит
            r = await c.put(
                f"/api/seller/bots/{bot_id}/shop-name",
                headers=seller_headers(),
                json={"shop_name": "х" * 65},
            )
            assert r.status_code == 422

            # чужой магазин не существует для чужого продавца
            await make_seller(db, telegram_id=222)
            r = await c.put(
                f"/api/seller/bots/{bot_id}/shop-name",
                headers=stranger_headers(),
                json={"shop_name": "Взлом"},
            )
            assert r.status_code == 404


# --- логотип -------------------------------------------------------------


async def _upload_logo(bot_id: int, data: bytes):
    async with client() as c:
        return await c.post(
            f"/api/seller/bots/{bot_id}/shop-logo",
            headers=seller_headers(),
            content=data,
        )


@pytest.mark.asyncio
async def test_upload_logo_upload_replace_delete(db):
    bot_id = await setup_shop(db)

    async with client() as c:
        # загрузка: адрес со случайным токеном, раздача без авторизации
        r = await _upload_logo(bot_id, PNG_BYTES)
        assert r.status_code == 200, r.text
        url = r.json()["url"]
        assert url.startswith("/api/shop-logos/")

        served = await c.get(url)
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("image/png")
        assert served.content == PNG_BYTES
        assert served.headers["x-content-type-options"] == "nosniff"

        # лого виден и в кабинете, и на витрине
        summary = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        assert summary.json()["logo_url"] == url
        store = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert store.json()["logo_url"] == url

        # повторная загрузка: новая строка на месте старой, старый адрес мёртв
        r = await _upload_logo(bot_id, JPEG_BYTES)
        assert r.status_code == 200, r.text
        second_url = r.json()["url"]
        assert second_url != url
        assert (await c.get(url)).status_code == 404
        logos = await _logo_rows(db)
        assert [l.token for l in logos] == [second_url.rsplit("/", 1)[-1]]

        # удаление: вернулись к букве
        r = await c.delete(f"/api/seller/bots/{bot_id}/shop-logo", headers=seller_headers())
        assert r.status_code == 200, r.text
        assert await _logo_rows(db) == []
        store = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert store.json()["logo_url"] is None


async def _logo_rows(db) -> list[ShopLogo]:
    async with db() as session:
        return (await session.execute(select(ShopLogo))).scalars().all()


@pytest.mark.asyncio
async def test_logo_rejects_bad_uploads(db):
    """Не-картинка, пустой файл и файл больше лимита отвергаются."""
    bot_id = await setup_shop(db)

    r = await _upload_logo(bot_id, b"<html>not an image</html>")
    assert r.status_code == 400
    assert "JPEG" in r.json()["detail"]

    r = await _upload_logo(bot_id, b"")
    assert r.status_code == 400

    r = await _upload_logo(bot_id, PNG_BYTES + b"0" * MAX_IMAGE_BYTES)
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_logo_requires_shop_owner(db):
    bot_id = await setup_shop(db)
    await make_seller(db, telegram_id=222)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/shop-logo",
            headers=stranger_headers(),
            content=PNG_BYTES,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_logo_survives_purge_orphan_images(db):
    """Чистка сирот касается только фото товаров — лого живёт вечно."""
    from datetime import datetime, timedelta, timezone

    from app.services.images import purge_orphan_images

    bot_id = await setup_shop(db)
    url = (await _upload_logo(bot_id, PNG_BYTES)).json()["url"]

    async with db() as session:
        for logo in (await session.execute(select(ShopLogo))).scalars():
            logo.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        await session.commit()

    assert await purge_orphan_images() == 0
    async with client() as c:
        assert (await c.get(url)).status_code == 200
