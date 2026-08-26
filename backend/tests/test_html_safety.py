"""Тексты для Telegram собираются с parse_mode=HTML.

Всё, что пришло от продавца (приветствие, текст кнопки) или из Telegram
(название канала), попадает в эти тексты как есть. Один символ «<» делает
сообщение неотправляемым: Telegram отвечает «can't parse entities», а
сообщение до продавца не доходит. Для меню настроек это фатально — оно
перестаёт открываться, и починить из бота уже нельзя.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.handlers.seller.channels import _channel_texts
from app.handlers.seller.settings import channel_text, settings_text

BROKEN = "Скидки <до 50%>"


def _bot(**over):
    base = dict(
        bot_username="shop_bot",
        show_catalog_button=True,
        catalog_button_text=None,
        welcome_text=None,
    )
    base.update(over)
    return SimpleNamespace(id=1, **base)


def test_settings_menu_survives_angle_brackets_in_welcome():
    text = settings_text(_bot(welcome_text=BROKEN), 0)
    assert "&lt;до 50%&gt;" in text
    assert "<до" not in text


def test_settings_menu_survives_angle_brackets_in_button_text():
    text = settings_text(_bot(catalog_button_text="<Каталог>"), 0)
    assert "&lt;Каталог&gt;" in text


def test_channel_card_survives_angle_brackets_in_title_and_greeting():
    channel = SimpleNamespace(
        id=1, title="Канал <VIP>", auto_accept=True, greeting_text=BROKEN
    )
    text = channel_text(channel)
    assert "Канал &lt;VIP&gt;" in text
    assert "&lt;до 50%&gt;" in text


def test_channel_connect_notifications_survive_angle_brackets():
    channel = SimpleNamespace(id=1, title="Канал <VIP>")
    for text in _channel_texts(channel, _bot(), invite_ok=True):
        assert "&lt;VIP&gt;" in text and "<VIP>" not in text



def test_long_text_is_truncated_before_escaping():
    """Срез не должен разрубать HTML-сущность вроде «&amp;» пополам."""
    text = settings_text(_bot(welcome_text="&" * 200), 0)
    assert "&am</i>" not in text and "&a</i>" not in text
    assert text.count("&amp;") == 120  # ровно срез в 120 исходных символов


@pytest.mark.asyncio
async def test_review_push_survives_angle_brackets():
    """Отзыв покупателя и название товара уходят продавцу в hub-бот с
    parse_mode=HTML: «<» в тексте оставил бы продавца без уведомления."""
    from app.services.reviews import notify_new_review

    sent = AsyncMock()
    with patch("app.bots.hub.hub_bot.send_message", new=sent):
        await notify_new_review(111, "Кроссовки <XL>", 5, "Носил <неделю> — норм")

    text = sent.await_args.args[1]
    assert "&lt;XL&gt;" in text and "&lt;неделю&gt;" in text
    assert "<XL>" not in text and "<неделю>" not in text


@pytest.mark.asyncio
async def test_fulfillment_push_survives_angle_brackets(db):
    """Трек, ссылка и примечание продавца тоже идут с parse_mode=HTML."""
    from tests.test_api import client, seller_headers
    from tests.test_fulfillment import paid_physical_order

    bot_id, order_id = await paid_physical_order(db)
    with patch("app.payments.service._notify", new=AsyncMock()) as notify_mock:
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"tracking": "RA<1>CN", "note": "размер <M>"},
            )
            assert r.status_code == 200, r.text

    text = notify_mock.call_args.args[2]
    assert "RA&lt;1&gt;CN" in text and "размер &lt;M&gt;" in text
    assert "<M>" not in text


@pytest.mark.asyncio
async def test_payment_push_survives_angle_brackets_in_title_and_url(db):
    """Сообщение об оплате — единственное, где покупатель получает digital-
    контент. «<» в названии товара или в ссылке выдачи роняло отправку целиком:
    деньги приняты, а покупатель не получал ни подтверждения, ни товар."""
    from tests.test_payments import make_order, patched_notifications
    from app.payments.service import handle_invoice_paid

    await make_order(
        db,
        title="Гайд <по настройке>",
        digital_url="https://guide.example/x?utm=a<b&c=d",
    )
    p1, p2 = patched_notifications()
    with p1 as notify_mock, p2:
        assert await handle_invoice_paid(555001, None) is True

    text = notify_mock.call_args.args[2]
    assert "Гайд &lt;по настройке&gt;" in text
    assert "https://guide.example/x?utm=a&lt;b&amp;c=d" in text
    # сырые «<» от данных продавца в текст не попадают (теги разметки — можно)
    assert "<по настройке>" not in text and "a<b" not in text
