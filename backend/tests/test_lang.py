"""Команда /lang: ручной выбор языка hub-бота и следование ему во всех текстах.

Правило языка (services/seller_texts.py): выбор в /lang главнее; без него
ru* -> RU, любой другой непустой language_code -> EN, а неизвестный язык —
RU (у покупателей наоборот: там EN — платформенный дефолт; hub всегда был
русским, и молча переводить существующих продавцов нельзя).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.handlers.hub import lang, mybots
from app.models import Seller
from app.services import seller_texts
from app.services.seller_texts import seller_locale, text
from tests.test_bot_connect import make_seller
from tests.test_hub_menus import (
    button_texts,
    fake_callback,
    fake_message,
    make_bot,
    patch_settings,
)


async def set_language(db, telegram_id: int, locale: str) -> None:
    async with db() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == telegram_id))
        ).scalar_one()
        seller.locale = locale
        await session.commit()


# --------------------------------------------------------------------------
# Правило языка
# --------------------------------------------------------------------------


def test_manual_choice_beats_telegram_language():
    assert seller_locale(SimpleNamespace(locale="en", language_code="ru")) == "en"
    assert seller_locale(SimpleNamespace(locale="ru", language_code="en")) == "ru"


def test_without_choice_ru_speakers_get_ru_others_en_unknown_ru():
    assert seller_locale(SimpleNamespace(locale=None, language_code="ru")) == "ru"
    assert seller_locale(SimpleNamespace(locale=None, language_code="en")) == "en"
    # осознанное различие с покупателями: неизвестный язык у продавца — RU
    assert seller_locale(SimpleNamespace(locale=None, language_code=None)) == "ru"
    assert seller_locale(None) == "ru"


def test_every_key_present_in_both_locales():
    missing = seller_texts.TEXTS["ru"].keys() ^ seller_texts.TEXTS["en"].keys()
    assert not missing, f"ключи текстов разъехались: {missing}"


def test_unknown_locale_falls_back_to_ru():
    # неизвестный язык в text() — RU: исторический язык hub-бота
    assert text("de", "msg.register") == text("ru", "msg.register")


# --------------------------------------------------------------------------
# /lang: команда, кнопки, сохранение выбора
# --------------------------------------------------------------------------


async def test_lang_shows_current_language_and_buttons(db):
    await make_seller(db)

    msg = fake_message()
    with patch(
        "app.handlers.hub.lang._seller_for",
        return_value=SimpleNamespace(locale=None, language_code="ru"),
    ):
        await lang.cmd_lang(msg)

    answer = msg.answer.await_args.args[0]
    assert "русский" in answer
    buttons = button_texts(lang.lang_keyboard())
    assert "🇷🇺 Русский" in buttons and "🇬🇧 English" in buttons


async def test_lang_prompt_comes_in_sellers_language(db):
    await make_seller(db)
    msg = fake_message()
    with patch(
        "app.handlers.hub.lang._seller_for",
        return_value=SimpleNamespace(locale=None, language_code="en"),
    ):
        await lang.cmd_lang(msg)
    assert "The language of this bot's messages" in msg.answer.await_args.args[0]


async def test_lang_set_persists_and_confirms_in_new_language(db):
    await make_seller(db)

    msg = fake_message()
    callback = fake_callback(msg, "lang:set:en")
    with patch("app.handlers.hub.lang.apply_chat_commands", new=AsyncMock()) as applied:
        await lang.set_lang(callback)

    # выбор записан
    async with db() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == 111))
        ).scalar_one()
        assert seller.locale == "en"
    # подтверждение уже на английском, меню команд перезаписано
    assert "Language switched to English" in msg.answer.await_args.args[0]
    applied.assert_awaited_once()


async def test_unknown_seller_gets_start_first_alert():
    callback = fake_callback(fake_message(), "lang:set:en", user_id=404404)
    await lang.set_lang(callback)
    args, kwargs = callback.answer.await_args
    assert args[0] == text("ru", "alert.start_first")
    assert kwargs["show_alert"] is True


# --------------------------------------------------------------------------
# Выбранный язык используют интерактивные тексты и пуши
# --------------------------------------------------------------------------


async def test_mybots_menu_follows_chosen_language(db):
    seller_id = await make_seller(db)
    await make_bot(db, seller_id, username="en_shop")
    await set_language(db, 111, "en")

    msg = fake_message()
    with patch_settings("mybots"):
        await mybots.send_shops_menu(msg, SimpleNamespace(id=seller_id, locale="en"))
    answer = msg.answer.await_args.args[0]
    assert "Your shops" in answer and "enabled" in answer
    buttons = button_texts(msg.answer.await_args.kwargs["reply_markup"])
    assert "➕ Connect another shop" in buttons


def test_push_texts_translate():
    revoked = seller_texts.text("en", "push.revoked.head", username="x") + seller_texts.text(
        "en", "push.revoked.managed"
    )
    assert "stopped receiving messages" in revoked
    assert "hasn't been shipped" in seller_texts.text("en", "push.stuck.one", hours=24)
    assert "has been sent to @CryptoBot" in seller_texts.text(
        "en", "push.payout_sent", amount="12", shop="shop"
    )
    assert "Add an admin" in seller_texts.text("en", "btn.add_admin")
