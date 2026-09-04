"""Профиль seller-бота в Telegram (services/bot_profile.py) и RU/EN настроек.

Telegram здесь не вызывается: Bot подменяется фейком, который записывает
вызовы и по желанию бросает нужное исключение. Проверяется контракт сервиса —
что именно уходит в Telegram и что возвращается кабинету, — а не aiogram.
БД тоже не нужна: сервис получает строку SellerBot и байты лого от вызывающего.
"""

import io
import types as pytypes

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramUnauthorizedError
from aiogram.methods import SetMyName
from PIL import Image

from app.models import SellerBot
from app.security import encrypt_bot_token
from app.services import bot_profile
from app.services.seller_texts import TEXTS, text

TOKEN = "123456:TEST-token-for-tests-only"


def _record(**overrides) -> SellerBot:
    fields = dict(
        id=7,
        seller_id=1,
        bot_username="petshop_bot",
        telegram_bot_id=123456,
        bot_token_encrypted=encrypt_bot_token(TOKEN),
        shop_name="Pet Shop",
        default_bot_name="petshop",
    )
    fields.update(overrides)
    return SellerBot(**fields)


class FakeBot:
    """Записывает вызовы; raise_with — исключение на любой метод."""

    instances: list["FakeBot"] = []

    def __init__(self, token: str, raise_with: Exception | None = None):
        self.token = token
        self.calls: list[tuple[str, dict]] = []
        self.raise_with = raise_with
        self.session = pytypes.SimpleNamespace(closed=False)

        async def close():
            self.session.closed = True

        self.session.close = close
        FakeBot.instances.append(self)

    async def _record_call(self, method: str, kw: dict):
        self.calls.append((method, kw))
        if self.raise_with is not None:
            raise self.raise_with

    async def set_my_name(self, **kw):
        await self._record_call("setMyName", kw)

    async def set_my_profile_photo(self, **kw):
        await self._record_call("setMyProfilePhoto", kw)

    async def remove_my_profile_photo(self, **kw):
        await self._record_call("removeMyProfilePhoto", kw)


@pytest.fixture
def fake_bot(monkeypatch):
    FakeBot.instances.clear()
    state = {"raise_with": None}

    def factory(token: str):
        return FakeBot(token, raise_with=state["raise_with"])

    monkeypatch.setattr(bot_profile, "Bot", factory)
    return state


def _png(width: int, height: int, color=(255, 0, 0, 128), mode="RGBA") -> bytes:
    img = Image.new(mode, (width, height), color)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# --------------------------------------------------------------------------
# Картинка
# --------------------------------------------------------------------------


def test_prepare_profile_photo_square_jpeg_from_landscape_png():
    jpeg = bot_profile.prepare_profile_photo(_png(1200, 400))
    with Image.open(io.BytesIO(jpeg)) as out:
        assert out.format == "JPEG"
        assert out.size == (640, 640)
        assert out.mode == "RGB"


def test_prepare_profile_photo_upscales_small_and_flattens_alpha_on_white():
    # полностью прозрачный PNG -> после наложения на белый должен стать белым
    jpeg = bot_profile.prepare_profile_photo(_png(64, 100, color=(0, 0, 0, 0)))
    with Image.open(io.BytesIO(jpeg)) as out:
        assert out.size == (640, 640)
        r, g, b = out.getpixel((320, 320))
        assert min(r, g, b) > 245


def test_prepare_profile_photo_rejects_garbage():
    with pytest.raises(ValueError):
        bot_profile.prepare_profile_photo(b"\xff\xd8\xff not really a jpeg")


# --------------------------------------------------------------------------
# Имя
# --------------------------------------------------------------------------


async def test_set_bot_name_calls_set_my_name(fake_bot):
    result = await bot_profile.set_bot_name(_record(), "Мой магазин")
    assert result.ok
    bot = FakeBot.instances[-1]
    assert bot.token == TOKEN
    assert bot.calls == [("setMyName", {"name": "Мой магазин"})]
    assert bot.session.closed  # сессия закрывается при любом исходе


async def test_reset_name_returns_default_bot_name(fake_bot):
    result = await bot_profile.set_bot_name(_record(default_bot_name="petshop"), None)
    assert result.ok
    assert FakeBot.instances[-1].calls == [("setMyName", {"name": "petshop"})]


async def test_reset_name_skipped_when_default_unknown(fake_bot):
    # бот подключён до миграции: во что переименовывать — неизвестно
    result = await bot_profile.set_bot_name(_record(default_bot_name=None), None)
    assert result.status == "skipped"
    assert FakeBot.instances == []  # к Telegram даже не ходили


async def test_draft_shop_is_skipped(fake_bot):
    result = await bot_profile.set_bot_name(_record(bot_token_encrypted=None), "X")
    assert result.status == "skipped"
    assert FakeBot.instances == []


def test_resolve_bot_name_truncates_to_64():
    assert bot_profile.resolve_bot_name(_record(), "a" * 100) == "a" * 64


# --------------------------------------------------------------------------
# Аватар
# --------------------------------------------------------------------------


async def test_set_bot_photo_sends_static_jpeg(fake_bot):
    result = await bot_profile.set_bot_photo(_record(), _png(300, 500))
    assert result.ok
    name, kw = FakeBot.instances[-1].calls[0]
    assert name == "setMyProfilePhoto"
    photo = kw["photo"]
    assert photo.type == "static"
    data = photo.photo.data
    with Image.open(io.BytesIO(data)) as out:
        assert out.format == "JPEG" and out.size == (640, 640)


async def test_set_bot_photo_bad_image_is_failed_not_raised(fake_bot):
    result = await bot_profile.set_bot_photo(_record(), b"not an image at all")
    assert result.status == "failed" and result.error == "bad_image"
    assert FakeBot.instances == []


async def test_remove_bot_photo(fake_bot):
    result = await bot_profile.remove_bot_photo(_record())
    assert result.ok
    assert FakeBot.instances[-1].calls == [("removeMyProfilePhoto", {})]


# --------------------------------------------------------------------------
# Ошибки Telegram не роняют запрос
# --------------------------------------------------------------------------


async def test_rate_limit_is_reported_with_retry_after(fake_bot):
    fake_bot["raise_with"] = TelegramRetryAfter(
        method=SetMyName(name="x"), message="Too Many Requests: retry after 3600", retry_after=3600
    )
    result = await bot_profile.set_bot_name(_record(), "New")
    assert result.status == "rate_limited"
    assert result.retry_after == 3600
    assert FakeBot.instances[-1].session.closed


@pytest.mark.parametrize(
    "exc",
    [
        TelegramUnauthorizedError(method=SetMyName(name="x"), message="Unauthorized"),
        TelegramForbiddenError(method=SetMyName(name="x"), message="Forbidden: bot was blocked"),
        RuntimeError("network down"),
    ],
)
async def test_telegram_failures_are_swallowed(fake_bot, exc):
    fake_bot["raise_with"] = exc
    result = await bot_profile.set_bot_name(_record(), "New")
    assert result.status == "failed"
    assert FakeBot.instances[-1].session.closed


async def test_sync_bot_profile_pushes_name_and_photo(fake_bot):
    results = await bot_profile.sync_bot_profile(_record(), _png(100, 100))
    assert results["name"].ok and results["photo"].ok
    names = [c[0] for bot in FakeBot.instances for c in bot.calls]
    assert names == ["setMyName", "setMyProfilePhoto"]


async def test_sync_without_logo_skips_photo(fake_bot):
    results = await bot_profile.sync_bot_profile(_record(), None)
    assert results["name"].ok and results["photo"].status == "skipped"


# --------------------------------------------------------------------------
# RU/EN настроек seller-бота
# --------------------------------------------------------------------------


def test_settings_keys_exist_in_both_locales():
    ru = {k for k in TEXTS["ru"] if k.startswith("settings.")}
    en = {k for k in TEXTS["en"] if k.startswith("settings.")}
    assert ru and ru == en


def test_settings_ru_strings_unchanged():
    # RU-строки байт-в-байт прежние: меню собиралось из этих же кусков
    assert text("ru", "settings.btn.welcome") == "✍️ Приветствие"
    assert text("ru", "settings.btn.close") == "✖️ Закрыть"
    assert text("ru", "settings.welcome.saved") == "✅ Приветствие сохранено"
    assert text("ru", "settings.button.saved") == "✅ Текст кнопки сохранён"
    assert text("ru", "settings.alert.channel_not_found") == "Канал не найден"
    menu = text(
        "ru", "settings.menu", username="petshop_bot", welcome="стандартное приветствие",
        button="Open", state="включена", channels=2,
    )
    assert menu == (
        "⚙️ <b>Настройки бота @petshop_bot</b>\n\n"
        "👋 Приветствие на /start:\n<i>стандартное приветствие</i>\n\n"
        "🔘 Кнопка «Open»: включена\n"
        "📢 Каналы для приёма заявок: 2"
    )


def test_settings_menu_follows_seller_locale():
    from app.handlers.seller.settings import OWNER_ONLY, settings_keyboard, settings_text

    bot = _record(show_catalog_button=True)
    ru_seller = pytypes.SimpleNamespace(locale="ru", language_code="en")
    en_seller = pytypes.SimpleNamespace(locale="en", language_code="ru")
    assert settings_text(bot, 0, ru_seller).startswith("⚙️ <b>Настройки бота @petshop_bot</b>")
    assert settings_text(bot, 0, en_seller).startswith("⚙️ <b>Settings of @petshop_bot</b>")
    en_buttons = [b.text for row in settings_keyboard(bot, 3, en_seller).inline_keyboard for b in row]
    assert en_buttons[:2] == ["✍️ Greeting", "🔘 Catalog button: on"]
    assert "📢 Channels (3)" in en_buttons
    # чужаку — по-прежнему русский алерт, вне словаря
    assert OWNER_ONLY == "Настройки доступны только владельцу магазина."
