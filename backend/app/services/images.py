"""Загрузка фото товаров: проверка содержимого вместо доверия клиенту.

Картинки лежат в БД (product_images), раздаются публично через
/api/images/{id}. Клиентскому content-type и имени файла не верим —
тип определяется по магическим байтам, всё вне белого списка отклоняется.
"""

# 5 МБ хватает для витрины и не даёт раздувать БД одним запросом
MAX_IMAGE_BYTES = 5 * 1024 * 1024

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
