"""Relay-чат по оплаченному заказу: доступ только сторон сделки, окно 72ч
после доставки, rate limit, анонимность, архивация, адресация в Telegram."""

import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models import ChatMessage, Customer, Order, OrderChat, Seller, SellerBot
from app.models.chat import ChatMessageArchive
from app.security import encrypt_bot_token
from app.services import chat as chat_service
from tests.test_payments import make_order, patched_notifications

SELLER_BOT_TOKEN = "111:token-for-tests-aaaaaaaaaaaaaaaaaaaaaa"
BUYER_TG = 777


def init_data_for(user: dict, key: str) -> str:
    from app.services.webapp_auth import sign_init_data

    return sign_init_data({"auth_date": int(time.time()), "user": user}, key)


def client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def seller_headers() -> dict:
    # кабинет подписан токеном hub-бота
    return {"X-Init-Data": init_data_for({"id": 111}, os.environ["HUB_BOT_TOKEN"])}


def buyer_headers(tg_id: int = BUYER_TG) -> dict:
    # витрина подписана токеном seller-бота магазина
    return {"X-Init-Data": init_data_for({"id": tg_id}, SELLER_BOT_TOKEN)}


async def pay_order(order_id: int, invoice_id: int = 555001) -> None:
    """Переводит заказ в оплаченные (digital — сразу delivered)."""
    from app.payments.service import handle_invoice_paid

    notify_patch, hub_patch = patched_notifications()
    with notify_patch, hub_patch:
        await handle_invoice_paid(invoice_id, None)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    chat_service._sends.clear()
    chat_service._last_send_at.clear()
    yield
    chat_service._sends.clear()
    chat_service._last_send_at.clear()


async def paid_physical_order(db, invoice_id: int = 555001) -> int:
    """Оплаченный физический заказ: чат открыт без дедлайна до доставки."""
    order_id = await make_order(
        db, product_type="physical", digital_url=None, invoice_id=invoice_id
    )
    await pay_order(order_id, invoice_id)
    return order_id


async def get_chat(bot_id: int, order_id: int):
    async with client() as c:
        return await c.get(
            f"/api/seller/bots/{bot_id}/orders/{order_id}/chat", headers=seller_headers()
        )


async def shop_id(db) -> int:
    async with db() as session:
        bot = (await session.execute(select(SellerBot))).scalars().first()
        return bot.id


# --------------------------------------------------------------------------
# Активация и доступ
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_activates_only_after_payment(db):
    order_id = await make_order(db)
    bot_id = await shop_id(db)

    r = await get_chat(bot_id, order_id)
    assert r.status_code == 403
    assert r.json()["detail"] == "chat_not_available"

    await pay_order(order_id)
    r = await get_chat(bot_id, order_id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["can_send"] is True
    assert body["messages"] == []


@pytest.mark.asyncio
async def test_seller_and_buyer_exchange_messages(db):
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    with patch("app.services.chat.notify_customer", new=AsyncMock(return_value=4242)):
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/chat/messages",
                headers=seller_headers(),
                json={"body": "Заказ собран, завтра отправлю"},
            )
    assert r.status_code == 200, r.text
    assert r.json()["sender"] == "seller"

    # покупатель видит сообщение продавца и отвечает
    async with client() as c:
        r = await c.get(
            f"/api/store/{bot_id}/orders/{order_id}/chat", headers=buyer_headers()
        )
    assert r.status_code == 200
    buyer_view = r.json()
    assert [m["body"] for m in buyer_view["messages"]] == ["Заказ собран, завтра отправлю"]

    async with client() as c:
        r = await c.post(
            f"/api/store/{bot_id}/orders/{order_id}/chat/messages",
            headers=buyer_headers(),
            json={"body": "Когда ждать доставку?"},
        )
    assert r.status_code == 200

    # продавец видит обе реплики в правильном порядке
    final = (await get_chat(bot_id, order_id)).json()
    assert [m["sender"] for m in final["messages"]] == ["seller", "customer"]


@pytest.mark.asyncio
async def test_foreign_seller_cannot_touch_other_shop_order(db):
    """Точный кейс из ТЗ: свой bot_id в пути, чужой order_id — 403."""
    await paid_physical_order(db, invoice_id=555101)
    my_bot = await shop_id(db)

    foreign_bot, foreign_chat = await second_order_with_chat(db)
    async with db() as session:
        foreign_order_id = (
            (await session.get(OrderChat, foreign_chat.id)).order_id
        )

    async with client() as c:
        r = await c.get(
            f"/api/seller/bots/{my_bot}/orders/{foreign_order_id}/chat",
            headers=seller_headers(),
        )
    assert r.status_code == 403
    assert r.json()["detail"] == "foreign order"

    # POST тоже закрыт
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{my_bot}/orders/{foreign_order_id}/chat/messages",
            headers=seller_headers(),
            json={"body": "чужой заказ"},
        )
    assert r.status_code == 403
    assert foreign_bot > 0


@pytest.mark.asyncio
async def test_foreign_buyer_gets_403(db):
    """Покупатель того же магазина не должен читать чужой заказ."""
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    async with client() as c:
        r = await c.get(
            f"/api/store/{bot_id}/orders/{order_id}/chat",
            headers=buyer_headers(tg_id=999),  # другой покупатель этого же бота
        )
    assert r.status_code == 403

    async with client() as c:
        r = await c.post(
            f"/api/store/{bot_id}/orders/{order_id}/chat/messages",
            headers=buyer_headers(tg_id=999),
            json={"body": "влез в чужой чат"},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_no_pii_leaks_into_chat_payload(db):
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    async with db() as session:
        customer = (
            await session.execute(select(Customer).where(Customer.telegram_id == BUYER_TG))
        ).scalar_one()
        customer.username = "secret_username"
        customer.first_name = "Секретное Имя"
        await session.commit()

    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/orders/{order_id}/chat/messages",
            headers=seller_headers(),
            json={"body": "тест"},
        )
    assert r.status_code == 200

    payload = (await get_chat(bot_id, order_id)).json()
    allowed_message_keys = {"id", "sender", "body", "created_at"}
    for message in payload["messages"]:
        assert set(message.keys()) <= allowed_message_keys
    assert "secret_username" not in str(payload)
    assert "Секретное Имя" not in str(payload)
    assert set(payload.keys()) == {"status", "can_send", "closes_at", "messages"}


# --------------------------------------------------------------------------
# Окно активности 72ч и блокировка
# --------------------------------------------------------------------------


async def backdate_delivery(db, order_id: int, status: str = "delivered", **delta) -> None:
    """Переводит заказ в доставленные и отматывает момент доставки."""
    async with db() as session:
        order = await session.get(Order, order_id)
        order.status = status
        order.delivered_at = datetime.now(timezone.utc) - timedelta(**delta)
        await session.commit()


@pytest.mark.asyncio
async def test_window_open_just_after_delivery(db):
    order_id = await make_order(db)  # digital: оплата = доставка
    await pay_order(order_id)
    await backdate_delivery(db, order_id, hours=71)
    bot_id = await shop_id(db)

    body = (await get_chat(bot_id, order_id)).json()
    assert body["can_send"] is True
    assert body["closes_at"] is not None

    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/orders/{order_id}/chat/messages",
            headers=seller_headers(),
            json={"body": "в окне"},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_window_expired_rejects_send_but_keeps_history(db):
    order_id = await make_order(db)
    await pay_order(order_id)
    await backdate_delivery(db, order_id, hours=73)
    bot_id = await shop_id(db)

    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/orders/{order_id}/chat/messages",
            headers=seller_headers(),
            json={"body": "поздно"},
        )
    assert r.status_code == 403
    assert r.json()["detail"] == "chat_locked"

    body = (await get_chat(bot_id, order_id)).json()
    assert body["can_send"] is False

    # фоновый джоб переводит чат в locked_by_timeout для выборок/UI
    locked = await chat_service.lock_expired_chats()
    assert locked >= 1
    async with db() as session:
        chat = (await session.execute(select(OrderChat))).scalar_one()
        assert chat.status == "locked_by_timeout"
        assert chat.locked_at is not None

    # история читается и после блокировки
    body = (await get_chat(bot_id, order_id)).json()
    assert body["status"] == "locked_by_timeout"


@pytest.mark.asyncio
async def test_cancelled_order_closes_chat(db):
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    async with db() as session:
        order = await session.get(Order, order_id)
        order.status = "cancelled"
        await session.commit()

    body = (await get_chat(bot_id, order_id)).json()
    assert body["can_send"] is False


# --------------------------------------------------------------------------
# Rate limiting и уведомления
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_returns_429(monkeypatch, db):
    monkeypatch.setattr(chat_service, "MIN_SEND_INTERVAL_SEC", 0.0)
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    last_status = None
    async with client() as c:
        for i in range(chat_service.MAX_MESSAGES_PER_WINDOW + 1):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/chat/messages",
                headers=seller_headers(),
                json={"body": f"спам {i}"},
            )
            last_status = r.status_code
            if r.status_code == 429:
                break
    assert last_status == 429


@pytest.mark.asyncio
async def test_seller_message_notifies_buyer_and_stores_tg_id(db):
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    notify = AsyncMock(return_value=4242)
    with patch("app.services.chat.notify_customer", new=notify):
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/chat/messages",
                headers=seller_headers(),
                json={"body": "<script>не экранируем здесь</script>"},
            )
    assert r.status_code == 200
    notify.assert_awaited_once()

    async with db() as session:
        message = (await session.execute(select(ChatMessage))).scalar_one()
        assert message.tg_message_id == 4242


@pytest.mark.asyncio
async def test_buyer_message_pushes_seller_via_hub(db):
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as hub_mock:
        async with client() as c:
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/chat/messages",
                headers=buyer_headers(),
                json={"body": "привет"},
            )
    assert r.status_code == 200
    hub_mock.assert_awaited_once()


# --------------------------------------------------------------------------
# Архивация
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_moves_messages_but_history_still_readable(db):
    order_id = await paid_physical_order(db)
    bot_id = await shop_id(db)

    with patch("app.services.chat.notify_customer", new=AsyncMock(return_value=None)):
        async with client() as c:
            await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/chat/messages",
                headers=seller_headers(),
                json={"body": "историческое сообщение"},
            )

    # закрываем чат и отматываем время блокировки за порог архивации
    await backdate_delivery(db, order_id, hours=73)
    await chat_service.lock_expired_chats()
    async with db() as session:
        chat = (await session.execute(select(OrderChat))).scalar_one()
        chat.locked_at = datetime.now(timezone.utc) - timedelta(days=31)
        await session.commit()

    moved = await chat_service.archive_old_chats()
    assert moved == 1

    async with db() as session:
        live_count = len((await session.execute(select(ChatMessage))).scalars().all())
        archived_count = len((await session.execute(select(ChatMessageArchive))).scalars().all())
    assert live_count == 0
    assert archived_count == 1

    # чтение прозрачно достаёт из архива
    body = (await get_chat(bot_id, order_id)).json()
    assert [m["body"] for m in body["messages"]] == ["историческое сообщение"]
    assert body["status"] == "archived"


# --------------------------------------------------------------------------
# Адресация в Telegram (хендлер relay)
# --------------------------------------------------------------------------


def make_tg_message(text: str, reply_to_message_id: int | None = None, message_id: int = 100):
    from aiogram import types

    reply = None
    if reply_to_message_id is not None:
        reply = types.Message.model_construct(
            message_id=reply_to_message_id,
        )
    message = types.Message.model_construct(
        message_id=message_id,
        text=text,
        chat=types.Chat.model_construct(id=BUYER_TG, type="private"),
        from_user=types.User.model_construct(id=BUYER_TG, is_bot=False, first_name="Buyer"),
        reply_to_message=reply,
    )
    # Message «заморожен» (pydantic frozen) — обычный setattr/patch.object на
    # инстансе падает; подсовываем мок answer напрямую в __dict__
    object.__setattr__(message, "answer", AsyncMock())
    return message


async def second_order_with_chat(db) -> tuple[int, OrderChat]:
    """Второй магазин+заказ того же покупателя (tg 777), чтобы проверить
    изоляцию магазинов и адресацию реплаев."""
    async with db() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == 111))
        ).scalar_one()
        bot = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=encrypt_bot_token("222:token-for-tests-bbbbbbbbbbbbbbbbbbbbbb"),
            bot_username="second_shop",
            telegram_bot_id=43,
        )
        session.add(bot)
        await session.flush()
        customer = Customer(telegram_id=BUYER_TG, seller_id=seller.id, bot_id=bot.id)
        session.add(customer)
        await session.flush()
        order = Order(
            seller_id=seller.id,
            bot_id=bot.id,
            customer_id=customer.id,
            status="paid",
            total=Decimal("10"),
            paid_at=datetime.now(timezone.utc),
        )
        session.add(order)
        await session.flush()
        chat = OrderChat(
            order_id=order.id, bot_id=bot.id, seller_id=seller.id, customer_id=customer.id
        )
        session.add(chat)
        await session.commit()
        return bot.id, chat


@pytest.mark.asyncio
async def test_handler_without_any_chats_is_silent(db):
    """Посторонний текст боту без чатов не получает ответа — как раньше."""
    from app.handlers.seller.chat import relay_buyer_message

    await make_order(db)  # заказ есть, но не оплачен — чат ещё не создан

    async with db() as session:
        customer = (
            await session.execute(select(Customer).where(Customer.telegram_id == BUYER_TG))
        ).scalar_one()
        bot = (await session.execute(select(SellerBot))).scalars().first()

    message = make_tg_message("случайный текст")
    await relay_buyer_message(message, customer=customer, bot_record=bot)
    message.answer.assert_not_awaited()

    async with db() as session:
        assert len((await session.execute(select(ChatMessage))).scalars().all()) == 0


@pytest.mark.asyncio
async def test_plain_text_goes_to_latest_open_chat(db):
    from app.handlers.seller.chat import relay_buyer_message

    order_id = await paid_physical_order(db)
    async with db() as session:
        bot = (await session.execute(select(SellerBot))).scalars().first()
        customer = (
            await session.execute(select(Customer).where(Customer.telegram_id == BUYER_TG))
        ).scalar_one()

    message = make_tg_message("обычный текст без реплая")
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
        await relay_buyer_message(message, customer=customer, bot_record=bot)

    async with db() as session:
        stored = (await session.execute(select(ChatMessage))).scalars().one()
        expected_chat = (
            await session.execute(select(OrderChat).where(OrderChat.order_id == order_id))
        ).scalar_one()
    assert stored.body == "обычный текст без реплая"
    assert stored.sender == "customer"
    assert stored.chat_id == expected_chat.id


@pytest.mark.asyncio
async def test_reply_addresses_exact_order_chat(db):
    """Реплай на сообщение конкретного заказа адресует именно его, даже если
    открыт более свежий чат другого заказа того же магазина."""
    from app.handlers.seller.chat import relay_buyer_message

    old_order = await paid_physical_order(db, invoice_id=555201)
    async with db() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == 111))
        ).scalar_one()
        bot = (await session.execute(select(SellerBot))).scalars().first()
        customer = (
            await session.execute(
                select(Customer).where(
                    Customer.telegram_id == BUYER_TG, Customer.bot_id == bot.id
                )
            )
        ).scalar_one()
        old_chat = OrderChat(
            order_id=old_order, bot_id=bot.id, seller_id=seller.id, customer_id=customer.id
        )
        session.add(old_chat)
        await session.flush()
        # второй заказ того же магазина и покупателя, его чат «новее»
        newer_order = Order(
            seller_id=seller.id,
            bot_id=bot.id,
            customer_id=customer.id,
            status="paid",
            total=Decimal("10"),
            paid_at=datetime.now(timezone.utc),
        )
        session.add(newer_order)
        await session.flush()
        newer_chat = OrderChat(
            order_id=newer_order.id, bot_id=bot.id, seller_id=seller.id, customer_id=customer.id
        )
        session.add(newer_chat)
        await session.flush()
        # сообщения продавца в обоих заказах, видимые покупателю в TG
        session.add(
            ChatMessage(
                chat_id=old_chat.id, sender="seller", body="старый заказ", tg_message_id=777001
            )
        )
        session.add(
            ChatMessage(
                chat_id=newer_chat.id, sender="seller", body="новый заказ", tg_message_id=888001
            )
        )
        await session.commit()
        newer_chat_id = newer_chat.id

    # реплай на сообщение НОВОГО заказа (не «последний открытый», а тот)
    message = make_tg_message("про новый заказ", reply_to_message_id=888001)
    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()):
        await relay_buyer_message(message, customer=customer, bot_record=bot)

    async with db() as session:
        stored = (
            await session.execute(select(ChatMessage).where(ChatMessage.sender == "customer"))
        ).scalars().one()
    assert stored.chat_id == newer_chat_id


@pytest.mark.asyncio
async def test_reply_from_other_customer_does_not_hijack_chat(db):
    """Реплай с message_id из чужого чата не адресует его: message_id в разных
    Telegram-диалогах совпадают, поэтому поиск жёстко скоупится на покупателя.
    У второго покупателя этого магазина чатов нет — тишина, ничего не записано."""
    from app.handlers.seller.chat import relay_buyer_message

    order_id = await paid_physical_order(db, invoice_id=555301)

    async with db() as session:
        bot = (await session.execute(select(SellerBot))).scalars().first()
        customer = (
            await session.execute(
                select(Customer).where(
                    Customer.telegram_id == BUYER_TG, Customer.bot_id == bot.id
                )
            )
        ).scalar_one()
        chat = OrderChat(
            order_id=order_id, bot_id=bot.id, seller_id=bot.seller_id, customer_id=customer.id
        )
        session.add(chat)
        await session.flush()
        other_customer = Customer(telegram_id=888, seller_id=bot.seller_id, bot_id=bot.id)
        session.add(other_customer)
        session.add(
            ChatMessage(chat_id=chat.id, sender="seller", body="моё сообщение", tg_message_id=555000)
        )
        await session.commit()

    message = make_tg_message("попытка угона", reply_to_message_id=555000)
    await relay_buyer_message(message, customer=other_customer, bot_record=bot)

    message.answer.assert_not_awaited()
    async with db() as session:
        bodies = [
            m.body for m in (await session.execute(select(ChatMessage))).scalars().all()
        ]
    assert "попытка угона" not in bodies
