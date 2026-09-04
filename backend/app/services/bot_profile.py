"""Профиль seller-бота в Telegram: имя и аватар вслед за настройками магазина.

До этого имя и логотип магазина жили только в шапке витрины, а сам бот в
Telegram оставался с тем именем и аватаркой, что продавец когда-то задал в
@BotFather (или без аватарки вовсе). Теперь кабинет — единственное место, где
продавец меняет идентичность магазина, и она доезжает до Telegram:

- смена имени (PUT /bots/{id}/shop-name)      -> setMyName
- загрузка лого (POST /bots/{id}/shop-logo)   -> setMyProfilePhoto (Bot API 9.x)
- удаление лого (DELETE /bots/{id}/shop-logo) -> removeMyProfilePhoto
- сброс имени (shop_name = null)              -> setMyName(default_bot_name)

Исходное Telegram-имя бота запоминается при подключении в
seller_bots.default_bot_name (getMe.first_name; у managed-бота — имя из
managed_bot_created). У ботов, подключённых до этого поля, оно пустое —
такой бот при сбросе не переименовывается (мы не знаем, во что), а профиль
догоняется при следующем изменении имени/лого или кнопкой «Профиль в
Telegram» в /settings самого бота.

Ошибки Telegram — отозванный токен, заблокированный бот, лимит частоты
смены имени (429) — логируются и возвращаются статусом, но никогда не
поднимаются наружу: запрос кабинета должен пройти, БД — источник правды,
Telegram — зеркало, которое можно обновить позже.

Pillow нужен только здесь: Telegram принимает статичный аватар лишь как
JPEG, а продавцы грузят PNG с прозрачностью, WebP и вертикальные фото.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from aiogram.types import BufferedInputFile, InputProfilePhotoStatic

from app.models import SellerBot
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)

# Сторона квадрата аватара. Telegram сам ужмёт что угодно, но 640 — размер,
# который он отдаёт в profile_photos как «big», больше грузить бессмысленно.
PROFILE_PHOTO_SIZE = 640
JPEG_QUALITY = 90
# Лимит setMyName (Bot API): до 64 символов
BOT_NAME_MAX = 64

SyncStatus = Literal["ok", "skipped", "rate_limited", "failed"]


@dataclass(frozen=True)
class SyncResult:
    """Исход одного вызова к Telegram. Возвращается, а не бросается: кабинет
    показывает тост по status, а запрос при любом исходе отвечает 200."""

    status: SyncStatus
    # для rate_limited: через сколько секунд Telegram готов принять смену имени
    retry_after: int | None = None
    # человекочитаемая причина для лога/ответа API (не для показа как есть)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def as_dict(self) -> dict:
        return {"status": self.status, "retry_after": self.retry_after, "error": self.error}


SKIPPED_DRAFT = SyncResult("skipped", error="draft")
SKIPPED_NO_DEFAULT = SyncResult("skipped", error="default_name_unknown")


# --------------------------------------------------------------------------
# Картинка: любой поддерживаемый формат -> квадратный JPEG 640×640
# --------------------------------------------------------------------------


def prepare_profile_photo(data: bytes, size: int = PROFILE_PHOTO_SIZE) -> bytes:
    """Привести загруженное лого к формату аватара Telegram.

    - EXIF-ориентация применяется (фото с телефона иначе ляжет боком);
    - у анимаций (GIF/WebP) берётся первый кадр;
    - центр-кроп до квадрата, затем ресайз до size×size (и вверх тоже:
      маленькое лого лучше размытое, чем отказ);
    - прозрачность кладётся на белый фон — JPEG альфу не умеет, а чёрный
      фон под прозрачным логотипом выглядит как ошибка.

    Бросает ValueError, если байты не картинка: вызывающий уже проверил
    магические байты (services/images.sniff_image_mime), так что сюда это
    попадает только при повреждённом файле.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as source:
            if getattr(source, "is_animated", False):
                source.seek(0)
            image = ImageOps.exif_transpose(source) or source
            image = image.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("не удалось прочитать изображение") from exc

    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    if side != size:
        image = image.resize((size, size), Image.LANCZOS)

    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    canvas.paste(image, mask=image.getchannel("A"))

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


# --------------------------------------------------------------------------
# Вызовы Telegram с единообразной обработкой ошибок
# --------------------------------------------------------------------------


def _bot_for(record: SellerBot) -> Bot | None:
    """Экземпляр Bot по зашифрованному токену; None у черновика без бота."""
    if record.bot_token_encrypted is None:
        return None
    return Bot(token=decrypt_bot_token(record.bot_token_encrypted))


async def _call(
    record: SellerBot, method: str, action: Callable[[Bot], Awaitable[object]]
) -> SyncResult:
    bot = _bot_for(record)
    if bot is None:
        return SKIPPED_DRAFT
    try:
        await action(bot)
        logger.info("Профиль seller-бота id=%s: %s ok", record.id, method)
        return SyncResult("ok")
    except TelegramRetryAfter as exc:
        # setMyName Telegram разрешает менять нечасто; это не ошибка, а «позже»
        logger.warning(
            "Профиль seller-бота id=%s: %s — лимит Telegram, retry_after=%s",
            record.id, method, exc.retry_after,
        )
        return SyncResult("rate_limited", retry_after=exc.retry_after, error="retry_after")
    except (TelegramUnauthorizedError, TelegramForbiddenError) as exc:
        # токен отозван в @BotFather либо бот заблокирован — сообщать нечего,
        # об этом продавцу отдельно расскажет bot_health
        logger.warning(
            "Профиль seller-бота id=%s: %s — токен недействителен: %s",
            record.id, method, exc,
        )
        return SyncResult("failed", error="unauthorized")
    except TelegramAPIError as exc:
        logger.warning("Профиль seller-бота id=%s: %s — ошибка Telegram: %s", record.id, method, exc)
        return SyncResult("failed", error=str(exc))
    except Exception:  # сеть, таймауты — что угодно, лишь бы не уронить запрос
        logger.exception("Профиль seller-бота id=%s: %s — неожиданная ошибка", record.id, method)
        return SyncResult("failed", error="unexpected")
    finally:
        await bot.session.close()


def resolve_bot_name(record: SellerBot, shop_name: str | None) -> str | None:
    """Какое имя должно стоять у бота в Telegram.

    Своё имя магазина — оно; при сбросе (None) — исходное из default_bot_name;
    если и его нет (бот подключён до миграции) — None: трогать имя нельзя,
    мы не знаем, во что его возвращать.
    """
    target = (shop_name or "").strip() or (record.default_bot_name or "").strip()
    return target[:BOT_NAME_MAX] or None


async def set_bot_name(record: SellerBot, shop_name: str | None) -> SyncResult:
    """setMyName: имя магазина -> имя бота. None = вернуть исходное имя."""
    target = resolve_bot_name(record, shop_name)
    if target is None:
        logger.info(
            "Профиль seller-бота id=%s: сброс имени пропущен — исходное имя неизвестно",
            record.id,
        )
        return SKIPPED_NO_DEFAULT
    return await _call(record, "setMyName", lambda bot: bot.set_my_name(name=target))


async def set_bot_photo(record: SellerBot, image: bytes) -> SyncResult:
    """setMyProfilePhoto: загруженное лого -> аватар бота."""
    try:
        jpeg = prepare_profile_photo(image)
    except ValueError:
        logger.exception("Профиль seller-бота id=%s: лого не удалось конвертировать", record.id)
        return SyncResult("failed", error="bad_image")
    photo = InputProfilePhotoStatic(photo=BufferedInputFile(jpeg, filename="logo.jpg"))
    return await _call(
        record, "setMyProfilePhoto", lambda bot: bot.set_my_profile_photo(photo=photo)
    )


async def remove_bot_photo(record: SellerBot) -> SyncResult:
    """removeMyProfilePhoto: лого удалено -> аватар снят."""
    return await _call(record, "removeMyProfilePhoto", lambda bot: bot.remove_my_profile_photo())


async def sync_bot_profile(record: SellerBot, logo: bytes | None) -> dict[str, SyncResult]:
    """Догнать профиль целиком: имя и аватар по текущему состоянию магазина.

    Для ботов, подключённых до появления синхронизации, и для случаев, когда
    отдельный вызов упал (лимит, сеть). Логотип передаётся байтами, чтобы
    сервис не лез в БД сам: вызывающий уже держит сессию.
    """
    name = await set_bot_name(record, record.shop_name)
    photo = await set_bot_photo(record, logo) if logo else SyncResult("skipped", error="no_logo")
    return {"name": name, "photo": photo}
