"""Аватар бота: фото магазина на витрине покупателя.

Telegram не отдаёт свои аватары по постоянному URL, поэтому при подключении
бота (и лениво — для магазинов, подключённых раньше этой фичи) скачиваем фото
и кладём байты в БД; витрина получает случайный токен-адрес, как у фото
товаров. Аватар — украшение: любая ошибка не должна ломать ни подключение
магазина, ни выдачу витрины, поэтому наверх исключение не идёт никогда.
"""

import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotAvatar, SellerBot
from app.security import decrypt_bot_token
from app.services.images import MAX_IMAGE_BYTES, sniff_image_mime

logger = logging.getLogger(__name__)

# Боты, у которых скачать аватар не удалось: не долбим Telegram на каждом
# открытии витрины. Свежая попытка — после переподключения бота или рестарта.
_failed_bots: set[int] = set()


async def fetch_avatar_bytes(
    bot_token: str, telegram_bot_id: int
) -> tuple[bytes, str] | None:
    """Фото бота из Telegram: (байты, mime). None — фото нет или не скачалось."""
    try:
        async with Bot(token=bot_token) as tg:
            chat = await tg.get_chat(telegram_bot_id)
            if chat.photo is None:
                return None
            buffer = await tg.download(chat.photo.big_file_id)
            data = buffer.getvalue()
    except Exception:
        logger.exception("Не удалось скачать аватар бота %s", telegram_bot_id)
        return None

    mime = sniff_image_mime(data)
    if mime is None or len(data) > MAX_IMAGE_BYTES:
        logger.warning(
            "Аватар бота %s не похож на картинку или слишком большой (%d байт)",
            telegram_bot_id,
            len(data),
        )
        return None
    return data, mime


async def refresh_bot_avatar(
    session: AsyncSession, bot: SellerBot, *, force: bool = False
) -> BotAvatar | None:
    """Тянет актуальное фото бота и заменяет строку аватара целиком — новый
    токен, чтобы immutable-кэш браузера не застрял на старой картинке.
    Коммит остаётся за вызывающим. Для ботов без аватара неудача запоминается:
    ленивый путь повторных попыток не делает (force=True — делает, так зовёт
    переподключение бота)."""
    if not force and bot.id in _failed_bots:
        return None

    avatar_bytes = await fetch_avatar_bytes(
        decrypt_bot_token(bot.bot_token_encrypted), bot.telegram_bot_id
    )
    if avatar_bytes is None:
        _failed_bots.add(bot.id)
        return None

    _failed_bots.discard(bot.id)
    data, mime = avatar_bytes

    old = (
        await session.execute(select(BotAvatar).where(BotAvatar.bot_id == bot.id))
    ).scalar_one_or_none()
    if old is not None:
        await session.delete(old)
        await session.flush()

    avatar = BotAvatar(bot_id=bot.id, mime=mime, size=len(data), data=data)
    session.add(avatar)
    await session.flush()
    return avatar
