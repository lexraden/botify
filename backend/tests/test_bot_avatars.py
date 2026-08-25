"""Аватар бота: хранение в БД, выдача витрине и публичная раздача по токену.
Живую докачку из Telegram не тестируем — fetch_avatar_bytes подменяется;
проверяем, что витрина получает адрес, байты раздаются, а неудача кэшируется
и не долбит Telegram на каждом открытии магазина."""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.db import get_session
from app.models import BotAvatar
from tests.test_api import buyer_headers, client, setup_shop


async def _give_avatar(bot_id: int) -> str:
    async with get_session() as session:
        avatar = BotAvatar(bot_id=bot_id, mime="image/png", size=4, data=b"\x89PNG")
        session.add(avatar)
        await session.commit()
        return avatar.token


@pytest.mark.asyncio
async def test_shop_exposes_avatar_url_and_it_is_served(db):
    bot_id = await setup_shop(db)
    token = await _give_avatar(bot_id)

    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert r.status_code == 200, r.text
        assert r.json()["shop_avatar_url"] == f"/api/bot-avatars/{token}"

        img = await c.get(f"/api/bot-avatars/{token}")
        assert img.status_code == 200
        assert img.content == b"\x89PNG"
        assert img.headers["content-type"] == "image/png"
        assert "immutable" in img.headers["cache-control"]
        assert img.headers["x-content-type-options"] == "nosniff"

        # чужой токен ничего не отдаёт
        assert (await c.get("/api/bot-avatars/unknown-token")).status_code == 404


@pytest.mark.asyncio
async def test_lazy_refresh_downloads_and_exposes_avatar(db):
    """У старого магазина без аватара фото докачивается прямо при выдаче витрины."""
    from app.services import bot_avatars

    bot_avatars._failed_bots.clear()
    bot_id = await setup_shop(db)
    fetched = (b"\xff\xd8\xffxx", "image/jpeg")

    with patch.object(
        bot_avatars, "fetch_avatar_bytes", new=AsyncMock(return_value=fetched)
    ):
        async with client() as c:
            r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
            assert r.status_code == 200, r.text
            url = r.json()["shop_avatar_url"]
            assert url and url.startswith("/api/bot-avatars/")

            img = await c.get(url)
            assert img.status_code == 200 and img.content == b"\xff\xd8\xffxx"

    async with get_session() as session:
        avatar = (await session.execute(select(BotAvatar))).scalar_one()
        assert avatar.bot_id == bot_id
        assert avatar.mime == "image/jpeg" and avatar.size == len(b"\xff\xd8\xffxx")


@pytest.mark.asyncio
async def test_failed_refresh_is_cached_and_not_retried(db):
    """Нет фото у бота — одну попытку делаем, дальше витрина отвечает без пауз."""
    from app.services import bot_avatars

    bot_avatars._failed_bots.clear()
    bot_id = await setup_shop(db)

    with patch.object(
        bot_avatars, "fetch_avatar_bytes", new=AsyncMock(return_value=None)
    ) as fetch:
        async with client() as c:
            for _ in range(2):
                r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
                assert r.status_code == 200
                assert r.json()["shop_avatar_url"] is None

    assert fetch.await_count == 1

    # переподключение (force=True) пробует снова несмотря на кэш неудачи
    from app.models import SellerBot

    with patch.object(
        bot_avatars,
        "fetch_avatar_bytes",
        new=AsyncMock(return_value=(b"\x89PNG", "image/png")),
    ):
        async with get_session() as session:
            bot = await session.get(SellerBot, bot_id)
            created = await bot_avatars.refresh_bot_avatar(session, bot, force=True)
            assert created is not None
