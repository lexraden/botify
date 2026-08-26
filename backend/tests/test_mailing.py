from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.db import get_session
from app.models import Customer, Mailing, Seller, SellerBot
from app.security import encrypt_bot_token
from app.services.mailing import process_due_mailings


async def setup_mailing(db, customer_ids=(1001, 1002, 1003)) -> int:
    async with db() as session:
        seller = Seller(telegram_id=111)
        session.add(seller)
        await session.flush()
        bot = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=encrypt_bot_token("111:mailing-test-token-aaaaaaaaaaaaaaaaaa"),
            bot_username="shop_bot",
            telegram_bot_id=42,
        )
        session.add(bot)
        await session.flush()
        for tg_id in customer_ids:
            session.add(Customer(telegram_id=tg_id, seller_id=seller.id, bot_id=bot.id))
        mailing = Mailing(seller_id=seller.id, bot_id=bot.id, text="Скидки!")
        session.add(mailing)
        await session.commit()
        return mailing.id


def fake_bot(send_mock):
    return SimpleNamespace(send_message=send_mock, session=SimpleNamespace(close=AsyncMock()))


@pytest.mark.asyncio
async def test_mailing_sends_to_all_customers(db):
    mailing_id = await setup_mailing(db)
    send = AsyncMock()
    with (
        patch("app.services.mailing.make_seller_bot", return_value=fake_bot(send)),
        patch("app.services.mailing.SEND_DELAY_SEC", 0),
    ):
        await process_due_mailings()

    assert send.await_count == 3
    async with get_session() as session:
        mailing = await session.get(Mailing, mailing_id)
        assert mailing.status == "done"
        assert mailing.sent_count == 3
        assert mailing.failed_count == 0


@pytest.mark.asyncio
async def test_blocked_user_marked_banned_and_skipped_next_time(db):
    mailing_id = await setup_mailing(db, customer_ids=(1001, 1002))

    async def send(chat_id, *args, **kwargs):
        if chat_id == 1002:
            raise TelegramForbiddenError(method=SimpleNamespace(), message="blocked")

    send_mock = AsyncMock(side_effect=send)
    with (
        patch("app.services.mailing.make_seller_bot", return_value=fake_bot(send_mock)),
        patch("app.services.mailing.SEND_DELAY_SEC", 0),
    ):
        await process_due_mailings()

    async with get_session() as session:
        mailing = await session.get(Mailing, mailing_id)
        assert mailing.sent_count == 1
        assert mailing.failed_count == 1
        seller = await session.get(Seller, mailing.seller_id)

        # заблокировавший бота — is_banned, следующая рассылка его не тронет
        from sqlalchemy import select

        banned = (
            await session.execute(select(Customer).where(Customer.is_banned.is_(True)))
        ).scalar_one()
        assert banned.telegram_id == 1002

        session.add(Mailing(seller_id=seller.id, bot_id=mailing.bot_id, text="Ещё раз"))
        await session.commit()

    send_mock2 = AsyncMock()
    with (
        patch("app.services.mailing.make_seller_bot", return_value=fake_bot(send_mock2)),
        patch("app.services.mailing.SEND_DELAY_SEC", 0),
    ):
        await process_due_mailings()
    assert send_mock2.await_count == 1
    assert send_mock2.call_args.args[0] == 1001


@pytest.mark.asyncio
async def test_long_mailing_marks_itself_alive_while_sending(db):
    """Идущая рассылка отмечается живой по ходу отправки.

    Без этого длинную рассылку по большой базе (0.06 с на сообщение — порог
    в 10 минут набирается на ~10 тысячах покупателей) джоб оживления счёл бы
    застрявшей и отправил заново, задвоив её части покупателей.
    """
    from app.services.mailing import revive_stuck_mailings

    mailing_id = await setup_mailing(db, customer_ids=(2001, 2002, 2003, 2004))
    seen: list[int] = []

    async def spy(mid: int) -> None:
        seen.append(mid)
        # рассылка «идёт давно»: без отметки её бы оживили
        async with get_session() as session:
            m = await session.get(Mailing, mid)
            m.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=30)
            await session.commit()
        await real_touch(mid)

    from app.services.mailing import _touch_heartbeat as real_touch

    with (
        patch("app.services.mailing.make_seller_bot", return_value=fake_bot(AsyncMock())),
        patch("app.services.mailing.SEND_DELAY_SEC", 0),
        patch("app.services.mailing.HEARTBEAT_EVERY", 2),
        patch("app.services.mailing._touch_heartbeat", new=spy),
    ):
        await process_due_mailings()

    assert seen == [mailing_id, mailing_id]  # после 2-го и 4-го покупателя

    # отметка свежая — оживлять нечего (рассылка уже done, но проверим явно)
    async with get_session() as session:
        mailing = await session.get(Mailing, mailing_id)
        mailing.status = "sending"
        await session.commit()
    assert await revive_stuck_mailings() == 0
