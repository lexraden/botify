"""Фоновое обслуживание: отозванные токены ботов, зависшие оплаченные заказы,
застрявшие в `sending` рассылки.

Общее у всех трёх — они чинят то, что ломается молча и потому не всплывает
ни в логах, ни в жалобах, пока не станет поздно.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramUnauthorizedError
from sqlalchemy import select

from app.models import Mailing, Order, Seller, SellerBot
from tests.test_payments import make_order, patched_notifications

# --------------------------------------------------------------------------
# Отозванный токен бота
# --------------------------------------------------------------------------


def _unauthorized() -> TelegramUnauthorizedError:
    return TelegramUnauthorizedError(method=None, message="Unauthorized")


@pytest.mark.asyncio
async def test_revoked_token_marks_bot_and_notifies_once(db):
    await make_order(db)
    from app.services.bot_health import check_revoked_tokens

    async with db() as session:
        bot = (await session.execute(select(SellerBot))).scalars().first()
        bot_id = bot.id

    hub = AsyncMock()
    with (
        patch("app.services.bot_health._token_is_alive", new=AsyncMock(return_value=False)),
        patch("app.bots.hub.hub_bot.send_message", new=hub),
    ):
        assert await check_revoked_tokens() == 1

    async with db() as session:
        assert (await session.get(SellerBot, bot_id)).webhook_status == "revoked"
    assert hub.await_count == 1
    assert "подключи" in hub.await_args.args[1].lower()

    # второй проход молчит: уведомление одно на отзыв, а не на каждый тик
    with (
        patch("app.services.bot_health._token_is_alive", new=AsyncMock(return_value=False)),
        patch("app.bots.hub.hub_bot.send_message", new=hub),
    ):
        assert await check_revoked_tokens() == 0
    assert hub.await_count == 1


@pytest.mark.asyncio
async def test_network_failure_does_not_mark_bot_revoked(db):
    """Telegram недоступен — это не про токен: пугать продавца нельзя."""
    await make_order(db)
    from app.services.bot_health import check_revoked_tokens

    hub = AsyncMock()
    with (
        patch("app.services.bot_health._token_is_alive", new=AsyncMock(return_value=None)),
        patch("app.bots.hub.hub_bot.send_message", new=hub),
    ):
        assert await check_revoked_tokens() == 0

    async with db() as session:
        bot = (await session.execute(select(SellerBot))).scalars().first()
        assert bot.webhook_status != "revoked"
    assert hub.await_count == 0


@pytest.mark.asyncio
async def test_unauthorized_from_telegram_reads_as_revoked():
    """401 от Telegram — токен отозван; прочие ошибки статус не трогают."""
    from app.services.bot_health import _token_is_alive

    class FakeBot:
        def __init__(self, exc):
            self._exc = exc
            self.session = AsyncMock()

        async def get_me(self):
            if self._exc:
                raise self._exc
            return object()

    with patch("app.bots.runner.make_seller_bot", side_effect=lambda t: FakeBot(_unauthorized())):
        assert await _token_is_alive("x") is False
    with patch("app.bots.runner.make_seller_bot", side_effect=lambda t: FakeBot(OSError("сеть"))):
        assert await _token_is_alive("x") is None
    with patch("app.bots.runner.make_seller_bot", side_effect=lambda t: FakeBot(None)):
        assert await _token_is_alive("x") is True


@pytest.mark.asyncio
async def test_webhook_restart_keeps_revoked_status(db):
    """Рестарт ставит вебхуки заново, но отозванный токен это не лечит:
    revoked нельзя понижать до failed — после каждого деплоя статус терял бы
    точность, а продавца снова звали переподключать уже отключённый магазин."""
    await make_order(db)
    from app.bots import runner

    async with db() as session:
        bot = (await session.execute(select(SellerBot))).scalars().first()
        bot.webhook_status = "revoked"
        await session.commit()

    setup = AsyncMock(return_value=False)
    with patch("app.bots.runner.setup_seller_webhook", new=setup):
        await runner.setup_all_seller_webhooks()

    async with db() as session:
        assert (await session.get(SellerBot, bot.id)).webhook_status == "revoked"
    setup.assert_not_awaited()

    # обычный (не отозванный) бот при рестарте обновляется как раньше
    async with db() as session:
        bot = await session.get(SellerBot, bot.id)
        bot.webhook_status = "failed"
        await session.commit()
    setup = AsyncMock(return_value=True)
    with patch("app.bots.runner.setup_seller_webhook", new=setup):
        await runner.setup_all_seller_webhooks()
    async with db() as session:
        assert (await session.get(SellerBot, bot.id)).webhook_status == "active"


# --------------------------------------------------------------------------
# Зависшие оплаченные заказы
# --------------------------------------------------------------------------


async def _paid_unfulfilled(db, hours_ago: float) -> int:
    """Оплаченный физический заказ, оплата — hours_ago часов назад."""
    order_id = await make_order(db, product_type="physical", digital_url=None)
    from app.payments.service import handle_invoice_paid

    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555001, None)

    async with db() as session:
        order = await session.get(Order, order_id)
        assert order.status == "paid"  # физический не уходит в delivered сам
        order.paid_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        await session.commit()
    return order_id


@pytest.mark.asyncio
async def test_stuck_paid_order_reminds_seller_once(db):
    order_id = await _paid_unfulfilled(db, hours_ago=30)
    from app.services.order_health import remind_stuck_orders

    hub = AsyncMock()
    with patch("app.bots.hub.hub_bot.send_message", new=hub):
        assert await remind_stuck_orders() == 1
    assert f"#{order_id}" in hub.await_args.args[1]

    async with db() as session:
        assert (await session.get(Order, order_id)).reminded_at is not None

    # повторный проход молчит — напоминание одно на заказ
    with patch("app.bots.hub.hub_bot.send_message", new=hub):
        assert await remind_stuck_orders() == 0
    assert hub.await_count == 1


@pytest.mark.asyncio
async def test_fresh_and_delivered_orders_are_not_reminded(db):
    """Свежий заказ ждать нормально, доставленный — уже не висит."""
    order_id = await _paid_unfulfilled(db, hours_ago=1)
    from app.services.order_health import remind_stuck_orders

    hub = AsyncMock()
    with patch("app.bots.hub.hub_bot.send_message", new=hub):
        assert await remind_stuck_orders() == 0

    async with db() as session:
        order = await session.get(Order, order_id)
        order.paid_at = datetime.now(timezone.utc) - timedelta(hours=99)
        order.status = "delivered"
        await session.commit()

    with patch("app.bots.hub.hub_bot.send_message", new=hub):
        assert await remind_stuck_orders() == 0
    assert hub.await_count == 0


@pytest.mark.asyncio
async def test_several_stuck_orders_come_as_one_message(db):
    """Десять пушей подряд читаются как спам — продавцу уходит один список."""
    first = await _paid_unfulfilled(db, hours_ago=30)
    from app.payments.service import handle_invoice_paid
    from app.services.order_health import remind_stuck_orders

    second = await make_order(
        db, product_type="physical", digital_url=None, total=Decimal("70"), invoice_id=555002
    )
    p1, p2 = patched_notifications()
    with p1, p2:
        await handle_invoice_paid(555002, None)
    async with db() as session:
        order = await session.get(Order, second)
        order.paid_at = datetime.now(timezone.utc) - timedelta(hours=40)
        await session.commit()

    hub = AsyncMock()
    with patch("app.bots.hub.hub_bot.send_message", new=hub):
        assert await remind_stuck_orders() == 2

    assert hub.await_count == 1  # один продавец — одно сообщение
    text = hub.await_args.args[1]
    assert f"#{first}" in text and f"#{second}" in text


# --------------------------------------------------------------------------
# Застрявшие рассылки
# --------------------------------------------------------------------------


async def _mailing(db, status: str, heartbeat_minutes_ago: float | None) -> int:
    async with db() as session:
        seller = (await session.execute(select(Seller))).scalars().first()
        bot = (await session.execute(select(SellerBot))).scalars().first()
        mailing = Mailing(
            seller_id=seller.id,
            bot_id=bot.id,
            text="Скидки",
            status=status,
            heartbeat_at=(
                None
                if heartbeat_minutes_ago is None
                else datetime.now(timezone.utc) - timedelta(minutes=heartbeat_minutes_ago)
            ),
        )
        session.add(mailing)
        await session.commit()
        return mailing.id


@pytest.mark.asyncio
async def test_stuck_mailing_returns_to_queue(db):
    await make_order(db)
    from app.services.mailing import revive_stuck_mailings

    stuck = await _mailing(db, "sending", heartbeat_minutes_ago=30)
    assert await revive_stuck_mailings() == 1

    async with db() as session:
        mailing = await session.get(Mailing, stuck)
        assert mailing.status == "pending"
        assert mailing.heartbeat_at is None


@pytest.mark.asyncio
async def test_live_mailing_is_left_alone(db):
    """Рассылка по большой базе идёт долго — по признаку жизни её не трогаем."""
    await make_order(db)
    from app.services.mailing import revive_stuck_mailings

    live = await _mailing(db, "sending", heartbeat_minutes_ago=1)
    done = await _mailing(db, "done", heartbeat_minutes_ago=99)

    assert await revive_stuck_mailings() == 0
    async with db() as session:
        assert (await session.get(Mailing, live)).status == "sending"
        assert (await session.get(Mailing, done)).status == "done"


@pytest.mark.asyncio
async def test_long_mailing_keeps_itself_alive(db):
    """Отправка обновляет признак жизни по ходу — иначе длинную рассылку
    оживили бы прямо на ходу и часть покупателей получила бы дубль."""
    await make_order(db)
    from app.services import mailing as mailing_service

    mailing_id = await _mailing(db, "sending", heartbeat_minutes_ago=30)
    await mailing_service._touch_heartbeat(mailing_id)

    assert await mailing_service.revive_stuck_mailings() == 0
    async with db() as session:
        assert (await session.get(Mailing, mailing_id)).status == "sending"
