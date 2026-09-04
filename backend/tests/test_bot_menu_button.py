"""Кнопка меню бота — постоянный вход в витрину (MenuButtonWebApp).

Ставится там же, где вебхук (setup_seller_webhook), переустанавливается при
смене текста кнопки в настройках и сбрасывается при выключении бота.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import types

from app.security import encrypt_bot_token

FAKE_SETTINGS = SimpleNamespace(
    webhook_base_url="https://api.example.com",
    telegram_webhook_secret="secret",
    effective_webapp_url="https://app.example.com",
)


def fake_bot(info_url: str) -> AsyncMock:
    bot = AsyncMock()
    bot.get_webhook_info.return_value = SimpleNamespace(url=info_url)
    return bot


def make_record(**kw) -> SimpleNamespace:
    defaults = dict(
        id=7,
        bot_token_encrypted=encrypt_bot_token("123456:TEST-TOKEN"),
        catalog_button_text=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


async def test_menu_button_points_to_shop_with_bot_id(db):
    from app.bots.runner import menu_button_for

    with patch("app.bots.runner.get_settings", return_value=FAKE_SETTINGS):
        menu = menu_button_for(make_record(catalog_button_text="🛒 Зайти в магазин"))

    assert isinstance(menu, types.MenuButtonWebApp)
    assert menu.text == "🛒 Зайти в магазин"
    assert menu.web_app.url == "https://app.example.com?bot_id=7"


async def test_menu_button_default_text_is_the_settings_default(db):
    """Без своего текста у продавца — тот же дефолт, что в настройках бота."""
    from app.bots.runner import menu_button_for
    from app.handlers.seller.settings import DEFAULT_BUTTON_TEXT

    with patch("app.bots.runner.get_settings", return_value=FAKE_SETTINGS):
        menu = menu_button_for(make_record())

    assert menu.text == DEFAULT_BUTTON_TEXT


async def test_menu_button_text_truncated_protectively(db):
    """catalog_button_text разрешает 64 символа, лимит Telegram на текст меню
    из кода не выводится — режем до тех же 64."""
    from app.bots.runner import menu_button_for

    with patch("app.bots.runner.get_settings", return_value=FAKE_SETTINGS):
        menu = menu_button_for(make_record(catalog_button_text="Ж" * 70))

    assert len(menu.text) == 64


@pytest.mark.asyncio
async def test_setup_seller_webhook_installs_menu_button():
    """Вход в витрину ставится вместе с вебхуком: рестарт и переподключение
    бота восстанавливают меню сами."""
    from app.bots.runner import setup_seller_webhook

    record = make_record(catalog_button_text="Открыть")
    bot = fake_bot("https://stale.example/webhook")  # чужой url — вебхук переставляется
    with (
        patch("app.bots.runner.get_settings", return_value=FAKE_SETTINGS),
        patch("app.bots.runner.make_seller_bot", return_value=bot),
    ):
        assert await setup_seller_webhook(record) is True

    bot.set_webhook.assert_awaited_once()
    menu = bot.set_chat_menu_button.await_args.kwargs["menu_button"]
    assert isinstance(menu, types.MenuButtonWebApp)
    assert menu.text == "Открыть"
    assert menu.web_app.url.endswith("?bot_id=7")


@pytest.mark.asyncio
async def test_menu_button_failure_does_not_break_webhook_setup():
    """Меню не поставилось (сеть, лимиты) — вебхук всё равно считается
    поднятым, рестарт повторит попытку."""
    from app.bots.runner import setup_seller_webhook

    record = make_record()
    bot = fake_bot("https://api.example.com/webhook/seller/7")
    bot.set_chat_menu_button.side_effect = RuntimeError("telegram down")
    with (
        patch("app.bots.runner.get_settings", return_value=FAKE_SETTINGS),
        patch("app.bots.runner.make_seller_bot", return_value=bot),
    ):
        assert await setup_seller_webhook(record) is True


@pytest.mark.asyncio
async def test_apply_menu_button_reports_failure():
    from app.bots.runner import apply_seller_menu_button

    record = make_record()
    bot = AsyncMock()
    bot.set_chat_menu_button.side_effect = RuntimeError("blocked")
    with (
        patch("app.bots.runner.get_settings", return_value=FAKE_SETTINGS),
        patch("app.bots.runner.make_seller_bot", return_value=bot),
    ):
        assert await apply_seller_menu_button(record) is False


@pytest.mark.asyncio
async def test_remove_seller_webhook_resets_menu_to_default():
    """Бот выключен — витрина убирается и из меню, а не остаётся мёртвой ссылкой."""
    from app.bots.runner import remove_seller_webhook

    record = make_record()
    bot = AsyncMock()
    with (
        patch("app.bots.runner.get_settings", return_value=FAKE_SETTINGS),
        patch("app.bots.runner.make_seller_bot", return_value=bot),
    ):
        await remove_seller_webhook(record)

    bot.delete_webhook.assert_awaited_once()
    assert isinstance(
        bot.set_chat_menu_button.await_args.kwargs["menu_button"], types.MenuButtonDefault
    )
