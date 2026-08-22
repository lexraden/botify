"""Публичная раздача загруженных фото товаров.

Картинки витрины и так видны покупателям, поэтому без авторизации; хранятся
только типы из белого списка (см. services/images.py), отдаются с nosniff,
чтобы браузер не пытался угадывать тип самостоятельно.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_api_session
from app.models import ProductImage

router = APIRouter()


@router.get("/images/{image_id}")
async def get_image(
    image_id: int,
    session: AsyncSession = Depends(get_api_session),
) -> Response:
    image = await session.get(ProductImage, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(
        content=image.data,
        media_type=image.mime,
        headers={
            # содержимое картинки по id не меняется — кэшируем навсегда;
            # замена фото у товара = загрузка новой картинки с новым id
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
