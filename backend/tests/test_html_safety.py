"""Тексты для Telegram собираются с parse_mode=HTML.

Всё, что пришло от продавца (приветствие, текст кнопки) или из Telegram
(название канала), попадает в эти тексты как есть. Один символ «<» делает
сообщение неотправляемым: Telegram отвечает «can't parse entities», а
сообщение до продавца не доходит. Для меню настроек это фатально — оно
перестаёт открываться, и починить из бота уже нельзя.
"""

from types import SimpleNamespace

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
