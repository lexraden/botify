"""Загрузка фото товаров: проверка содержимого вместо доверия клиенту.

Картинки лежат в БД (product_images), раздаются публично через
/api/images/{id}. Клиентскому content-type и имени файла не верим —
тип определяется по магическим байтам, всё вне белого списка отклоняется.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, select

from app.db import get_session
from app.models import Product, ProductImage, ProductVariant

logger = logging.getLogger(__name__)

# 5 МБ хватает для витрины и не даёт раздувать БД одним запросом
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Префикс адреса картинки и в products.image_url, и в списках вариаций
_IMAGE_URL_PREFIX = "/api/images/"

# Сколько сирота ждёт удаления: фото могло быть загружено, а форма товара
# ещё не сохранена — гард от удаления картинки «на ровном месте».
ORPHAN_GRACE_HOURS = 24

_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_image_mime(data: bytes) -> str | None:
    """Тип картинки по содержимому; None — не картинка из белого списка."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    return None


async def purge_orphan_images(older_than_hours: int = ORPHAN_GRACE_HOURS) -> int:
    """Удалить фото, на которые не ссылается ни один товар и ни одна вариация.

    Фото попадает в БД при загрузке, а в товар записывается только при
    сохранении формы: бросил форму, упал браузер, товар удалили — байты
    оставались в БД навсегда. Ссылка хранится текстом в products.image_url
    («/api/images/{token}»), внешнего ключа нет, поэтому коррелированный
    NOT EXISTS. У товара с вариациями свой список адресов лежит ещё и в
    product_variants.images — без него чистка удаляла фото второй и следующих
    вариаций: защищено там только первое, скопированное в products.image_url.
    Адреса вариаций разбираются в питоне, а не операторами JSONB: чистка
    обязана работать одинаково на Postgres и SQLite (тесты). Фото чатов
    (chat_images) не трогаем: на их токены ссылается архив переписки.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    async with get_session() as session:
        variant_tokens = {
            url[len(_IMAGE_URL_PREFIX):]
            for (images,) in (
                await session.execute(select(ProductVariant.images))
            ).all()
            for url in (images or [])
            if isinstance(url, str) and url.startswith(_IMAGE_URL_PREFIX)
        }
        conditions = [
            ProductImage.created_at < cutoff,
            ~exists(
                select(Product.id).where(
                    Product.image_url == _IMAGE_URL_PREFIX + ProductImage.token,
                )
            ),
        ]
        # пустой not_in SQLAlchemy трактует как «не удалять ничего», поэтому
        # условие добавляем только при наличии защищённых токенов
        if variant_tokens:
            conditions.append(ProductImage.token.not_in(variant_tokens))
        result = await session.execute(delete(ProductImage).where(*conditions))
        await session.commit()
    if result.rowcount:
        logger.info("Удалено осиротевших фото товаров: %d", result.rowcount)
    return result.rowcount
