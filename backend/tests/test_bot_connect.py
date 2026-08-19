from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Seller, SellerBot
from app.security import decrypt_bot_token
from app.services.bot_connect import connect_seller_bot

VALID_TOKEN = "1234567890:AAEhBOweik6ad9r_QXMENQknvqfy9HdKWvs"


def mock_get_me(bot_id=987654321, username="test_shop_bot"):
    return patch(
        "app.services.bot_connect.Bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(id=bot_id, username=username)),
    )


async def make_seller(db, telegram_id=111) -> int:
    async with db() as session:
        seller = Seller(telegram_id=telegram_id)
        session.add(seller)
        await session.commit()
        return seller.id


@pytest.mark.asyncio
async def test_rejects_bad_format(db):
    result = await connect_seller_bot(1, "definitely not a token")
    assert not result.ok
    assert result.error == "bad_format"


@pytest.mark.asyncio
async def test_rejects_revoked_token(db):
    seller_id = await make_seller(db)
    with patch(
        "app.services.bot_connect.Bot.get_me",
        new=AsyncMock(side_effect=Exception("Unauthorized")),
    ):
        result = await connect_seller_bot(seller_id, VALID_TOKEN)
    assert not result.ok
    assert result.error == "get_me_failed"


@pytest.mark.asyncio
async def test_connect_success_encrypts_token_and_finishes_onboarding(db):
    seller_id = await make_seller(db)
    with mock_get_me():
        result = await connect_seller_bot(seller_id, VALID_TOKEN)

    assert result.ok
    assert result.bot_username == "test_shop_bot"

    async with db() as session:
        record = (await session.execute(select(SellerBot))).scalar_one()
        # в БД нет plaintext-токена, но расшифровка возвращает оригинал
        assert VALID_TOKEN.encode() not in record.bot_token_encrypted
        assert decrypt_bot_token(record.bot_token_encrypted) == VALID_TOKEN
        assert record.telegram_bot_id == 987654321
        # без WEBHOOK_BASE_URL вебхук не ставится — статус pending
        assert record.webhook_status == "pending"

        seller = await session.get(Seller, seller_id)
        assert seller.onboarding_step == "bot_done"


@pytest.mark.asyncio
async def test_same_bot_twice_by_same_seller(db):
    seller_id = await make_seller(db)
    with mock_get_me():
        first = await connect_seller_bot(seller_id, VALID_TOKEN)
        second = await connect_seller_bot(seller_id, VALID_TOKEN)

    assert first.ok
    assert not second.ok
    assert second.error == "already_yours"
    assert second.bot_username == "test_shop_bot"


@pytest.mark.asyncio
async def test_same_bot_by_another_seller_is_rejected(db):
    seller_a = await make_seller(db, telegram_id=111)
    seller_b = await make_seller(db, telegram_id=222)
    with mock_get_me():
        first = await connect_seller_bot(seller_a, VALID_TOKEN)
        second = await connect_seller_bot(seller_b, VALID_TOKEN)

    assert first.ok
    assert not second.ok
    assert second.error == "taken_by_other"
