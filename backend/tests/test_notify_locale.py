"""Язык покупательских уведомлений — «как в Mini App»: ручной выбор языка в
профиле главнее, без него русский идёт тем, у кого Telegram настроен на
русский (language_code ru*), остальным — английский. Здесь проверяются и
правила выбора, и транспорт выбора (заголовок X-Locale), и сами пуши."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Customer
from app.services.notify_texts import buyer_locale, text

from tests.test_api import (
    buyer_headers,
    client,
    seller_headers,
    setup_shop,
)
from tests.test_fulfillment import paid_physical_order


def _customer(language_code=None, locale=None) -> Customer:
    return Customer(
        telegram_id=1, seller_id=1, bot_id=1, language_code=language_code, locale=locale
    )


@pytest.mark.parametrize(
    "language_code,expected",
    [("ru", "ru"), ("RU", "ru"), ("ru-RU", "ru"), ("uk", "en"), ("en", "en"), (None, "en")],
)
def test_without_manual_choice_language_follows_telegram(language_code, expected):
    assert buyer_locale(_customer(language_code=language_code)) == expected


def test_manual_choice_beats_telegram_language():
    assert buyer_locale(_customer(language_code="ru", locale="en")) == "en"
    assert buyer_locale(_customer(language_code="uk", locale="ru")) == "ru"


@pytest.mark.parametrize("locale", ["zz", "", None])
def test_unknown_locale_falls_back_to_english(locale):
    assert text(locale, "chat.header", id=5) == "💬 Order #5"


@pytest.mark.asyncio
async def test_x_locale_header_persists_and_beats_telegram_language(db):
    """Ручной выбор из Mini App сохраняется в базе и главнее языка Telegram."""
    bot_id, order_id = await paid_physical_order(db)  # покупатель ru по Telegram
    async with client() as c:
        r = await c.get(
            f"/api/store/{bot_id}/orders/my",
            headers={**buyer_headers(), "X-Locale": "en"},
        )
        assert r.status_code == 200
    async with db() as session:
        customer = (await session.execute(select(Customer))).scalar_one()
        assert customer.locale == "en"

    # мусорное значение существующий выбор не сбрасывает
    async with client() as c:
        r = await c.get(
            f"/api/store/{bot_id}/orders/my",
            headers={**buyer_headers(), "X-Locale": "zz"},
        )
        assert r.status_code == 200
    async with db() as session:
        customer = (await session.execute(select(Customer))).scalar_one()
        assert customer.locale == "en"

    # пуш об отправке теперь английский, хотя Telegram у покупателя русский
    with patch("app.payments.service._notify", new=AsyncMock()) as notify_mock:
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"value": "RA123456789CN"},
            )
            assert r.status_code == 200, r.text
    push_text = notify_mock.call_args.args[2]
    assert f"📦 The seller shipped order #{order_id}!" in push_text
    assert "mark it received" in push_text
    assert "RA123456789CN" in push_text


@pytest.mark.asyncio
async def test_foreign_buyer_gets_english_push_and_note(db):
    """Иностранцу (language_code uk) — английский пуш и английская запись в чате."""
    bot_id, order_id = await paid_physical_order(db)

    from app.db import get_session

    async with get_session() as session:
        customer = (await session.execute(select(Customer))).scalar_one()
        customer.language_code = "uk"
        await session.commit()

    with patch("app.payments.service._notify", new=AsyncMock()) as notify_mock:
        async with client() as c:
            # только фото, без трека: фото-строка живёт в ветке elif
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"photos": 2},
            )
            assert r.status_code == 200, r.text
            history = (
                await c.get(
                    f"/api/seller/bots/{bot_id}/orders/{order_id}/chat",
                    headers=seller_headers(),
                )
            ).json()

    push_text = notify_mock.call_args.args[2]
    assert f"📦 The seller shipped order #{order_id}!" in push_text
    assert "Parcel photos below (2)." in push_text
    assert "mark it received" in push_text

    note = history["messages"][0]["body"]
    assert f"📦 Order #{order_id} shipped." in note
    assert "Parcel photos below (2)." in note


@pytest.mark.asyncio
async def test_paid_push_is_english_without_telegram_language(db):
    """Покупатель без language_code (и без ручного выбора) — английское
    подтверждение оплаты: дефолт платформы EN."""
    from app.payments.service import handle_invoice_paid
    from tests.test_payments import make_order, patched_notifications

    order_id = await make_order(db, product_type="physical", digital_url=None)
    p1, p2 = patched_notifications()
    with p1 as notify_mock, p2:
        await handle_invoice_paid(555001, None)

    push_text = notify_mock.call_args.args[2]
    assert f"✅ Order #{order_id} paid!" in push_text
    assert "The seller is preparing your order" in push_text
