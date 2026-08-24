"""Публичная раздача загруженных фото товаров.

Картинки витрины и так видны покупателям, поэтому без авторизации; хранятся
только типы из белого списка (см. services/images.py), отдаются с nosniff,
чтобы браузер не пытался угадывать тип самостоятельно.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_api_session
from app.models import ProductImage

router = APIRouter()


@router.get("/images/{token}")
async def get_image(
    token: str,
    session: AsyncSession = Depends(get_api_session),
) -> Response:
    image = (
        await session.execute(select(ProductImage).where(ProductImage.token == token))
    ).scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(
        content=image.data,
        media_type=image.mime,
        headers={
            # адрес картинки — случайный токен и никогда не переиспользуется,
            # поэтому кэшировать навсегда безопасно даже после сброса базы
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
