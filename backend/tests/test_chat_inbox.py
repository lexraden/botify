"""Инбокс продавца: список переписок и непрочитанные.

До этого списка не было вовсе — в чат продавец попадал только из строки
заказа. Главное, что проверяется, — счётчик новых: ради ответа на «есть ли
новые» инбокс и открывают, и врущий счётчик хуже отсутствующего.
"""

import pytest
from sqlalchemy import select

from app.models import ChatMessage, Order, OrderChat, SellerBot
from app.services import chat as chat_service
from tests.test_order_chat import (
    _reset_rate_limiter,  # noqa: F401 — автофикстура рейт-лимитера
    client,
    paid_physical_order,
    seller_headers,
)


async def bot_id_of(db) -> int:
    async with db() as session:
        return (await session.execute(select(SellerBot))).scalars().first().id


async def say(db, order_id: int, sender: str, body: str) -> None:
    """Сообщение в чат заказа от лица стороны, минуя API и рейт-лимит."""
    async with db() as session:
        order = await session.get(Order, order_id)
        chat = await chat_service.get_or_create_chat(session, order)
        session.add(ChatMessage(chat_id=chat.id, sender=sender, body=body))
        await session.commit()


async def inbox(bot_id: int):
    async with client() as c:
        r = await c.get(f"/api/seller/bots/{bot_id}/chats", headers=seller_headers())
    assert r.status_code == 200, r.text
    return r.json()


async def open_chat(bot_id: int, order_id: int):
    async with client() as c:
        r = await c.get(
            f"/api/seller/bots/{bot_id}/orders/{order_id}/chat", headers=seller_headers()
        )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_empty_inbox(db):
    """Переписок нет — пустой список, а не ошибка."""
    await paid_physical_order(db)
    assert await inbox(await bot_id_of(db)) == []


@pytest.mark.asyncio
async def test_unread_counts_only_customer_messages(db):
    """Свои же сообщения продавцу непрочитанными быть не могут."""
    order_id = await paid_physical_order(db)
    bot_id = await bot_id_of(db)
    await say(db, order_id, "customer", "Когда отправите?")
    await say(db, order_id, "seller", "Сегодня")
    await say(db, order_id, "customer", "Спасибо")

    row = (await inbox(bot_id))[0]
    assert row["order_id"] == order_id
    assert row["unread"] == 2
    assert row["last_message"] == "Спасибо" and row["last_sender"] == "customer"


@pytest.mark.asyncio
async def test_opening_the_chat_marks_it_read(db):
    """Открыл переписку — она прочитана. Отдельной кнопки нет: она означала
    бы, что список врёт до нажатия."""
    order_id = await paid_physical_order(db)
    bot_id = await bot_id_of(db)
    await say(db, order_id, "customer", "Привет")
    assert (await inbox(bot_id))[0]["unread"] == 1

    await open_chat(bot_id, order_id)
    assert (await inbox(bot_id))[0]["unread"] == 0


@pytest.mark.asyncio
async def test_new_message_after_reading_is_unread_again(db):
    order_id = await paid_physical_order(db)
    bot_id = await bot_id_of(db)
    await say(db, order_id, "customer", "Первое")
    await open_chat(bot_id, order_id)

    await say(db, order_id, "customer", "Второе")
    row = (await inbox(bot_id))[0]
    assert row["unread"] == 1
    assert row["last_message"] == "Второе"


@pytest.mark.asyncio
async def test_sorted_by_freshness(db):
    """Свежие сверху: инбокс читают с начала."""
    old_order = await paid_physical_order(db, invoice_id=555001)
    new_order = await paid_physical_order(db, invoice_id=555002)
    bot_id = await bot_id_of(db)
    await say(db, old_order, "customer", "старое")
    await say(db, new_order, "customer", "свежее")

    rows = await inbox(bot_id)
    assert [r["order_id"] for r in rows] == [new_order, old_order]


@pytest.mark.asyncio
async def test_photo_without_caption_is_not_an_empty_row(db):
    """Фото без подписи лежит с пустым body — строка списка не должна быть
    пустой, иначе выглядит как сбой."""
    order_id = await paid_physical_order(db)
    bot_id = await bot_id_of(db)
    async with db() as session:
        order = await session.get(Order, order_id)
        chat = await chat_service.get_or_create_chat(session, order)
        session.add(ChatMessage(chat_id=chat.id, sender="customer", body="", image_token="t"))
        await session.commit()

    assert (await inbox(bot_id))[0]["last_message"] == "📷"


@pytest.mark.asyncio
async def test_foreign_shop_sees_nothing(db):
    """Изоляция по магазину — как везде в кабинете."""
    order_id = await paid_physical_order(db)
    await say(db, order_id, "customer", "секрет")
    async with db() as session:
        seller_id = (await session.execute(select(SellerBot))).scalars().first().seller_id
        other = SellerBot(
            seller_id=seller_id,
            bot_token_encrypted=b"x",
            bot_username="other_shop",
            telegram_bot_id=4343,
        )
        session.add(other)
        await session.commit()
        other_id = other.id

    assert await inbox(other_id) == []


@pytest.mark.asyncio
async def test_closed_window_is_visible_but_not_writable(db):
    """Закрытый чат из списка не пропадает: история нужна обеим сторонам."""
    from datetime import datetime, timedelta, timezone

    order_id = await paid_physical_order(db)
    bot_id = await bot_id_of(db)
    await say(db, order_id, "customer", "давно")
    async with db() as session:
        order = await session.get(Order, order_id)
        order.status = "delivered"
        order.delivered_at = datetime.now(timezone.utc) - timedelta(days=30)
        await session.commit()

    row = (await inbox(bot_id))[0]
    assert row["can_send"] is False
    assert row["unread"] == 1  # прочитать всё ещё нужно


# --------------------------------------------------------------------------
# Пуш продавцу: кнопка в нужный магазин и превью сообщения
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_carries_button_into_the_right_shop(db):
    """Раньше пуш говорил «открой кабинет» словами, и продавец искал его
    руками. Кнопка ведёт прямо в «Сообщения» этого магазина."""
    from unittest.mock import AsyncMock, patch

    from app.config import get_settings
    from app.services.chat import notify_seller

    await paid_physical_order(db)
    bot_id = await bot_id_of(db)
    settings = get_settings().model_copy(update={"webapp_url": "https://app.example"})
    with (
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send,
        patch("app.config.get_settings", return_value=settings),
    ):
        await notify_seller(111, 12, locale="ru", bot_id=bot_id, body="Когда отправите?")

    kwargs = send.await_args.kwargs
    button = kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.web_app.url == f"https://app.example/shop/{bot_id}?tab=messages"
    # первые слова покупателя видно сразу — не открывая кабинет
    assert "Когда отправите?" in send.await_args.args[1]


@pytest.mark.asyncio
async def test_push_escapes_the_buyers_text(db):
    """Текст пишет покупатель, а пуш уходит с parse_mode=HTML: один «<»
    оставил бы продавца вообще без уведомления."""
    from unittest.mock import AsyncMock, patch

    from app.services.chat import notify_seller

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        await notify_seller(111, 12, locale="ru", bot_id=1, body="<b>жирный</b> <script>")

    text = send.await_args.args[1]
    assert "<b>жирный</b>" not in text
    assert "&lt;script&gt;" in text


@pytest.mark.asyncio
async def test_long_message_is_cut_in_the_push(db):
    """Пуш — повод открыть кабинет, а не второй экземпляр переписки."""
    from unittest.mock import AsyncMock, patch

    from app.services.chat import PREVIEW_LEN, notify_seller

    with patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send:
        await notify_seller(111, 12, locale="ru", bot_id=1, body="я" * 500)

    text = send.await_args.args[1]
    assert "…" in text
    assert text.count("я") <= PREVIEW_LEN


@pytest.mark.asyncio
async def test_push_without_webapp_url_still_goes(db):
    """Без WEBAPP_URL кнопку строить не из чего — уведомление всё равно
    должно дойти, а не потеряться."""
    from unittest.mock import AsyncMock, patch

    from app.config import get_settings
    from app.services.chat import notify_seller

    settings = get_settings().model_copy(update={"webapp_url": ""})
    with (
        patch("app.bots.hub.hub_bot.send_message", new=AsyncMock()) as send,
        patch("app.config.get_settings", return_value=settings),
    ):
        await notify_seller(111, 12, locale="ru", bot_id=1, body="привет")

    assert send.await_count == 1
    assert send.await_args.kwargs["reply_markup"] is None
