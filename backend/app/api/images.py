"""Публичная раздача загруженных фото товаров и картинок переписки.

Картинки витрины и так видны покупателям; адрес фото в чате — случайный
неугадываемый токен, как у витрины. Хранятся только типы из белого списка
(см. services/images.py), отдаются с nosniff, чтобы браузер не пытался
угадывать тип самостоятельно.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_api_session
from app.models import ChatImage, ProductImage, ShopLogo

router = APIRouter()

# адрес картинки — случайный токен и никогда не переиспользуется,
# поэтому кэшировать навсегда безопасно даже после сброса базы
_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
}


def _image_response(data: bytes, mime: str) -> Response:
    return Response(content=data, media_type=mime, headers=_CACHE_HEADERS)


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
    return _image_response(image.data, image.mime)


@router.get("/chat-images/{token}")
async def get_chat_image(
    token: str,
    session: AsyncSession = Depends(get_api_session),
) -> Response:
    image = (
        await session.execute(select(ChatImage).where(ChatImage.token == token))
    ).scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=404, detail="image not found")
    return _image_response(image.data, image.mime)


@router.get("/shop-logos/{token}")
async def get_shop_logo(
    token: str,
    session: AsyncSession = Depends(get_api_session),
) -> Response:
    logo = (
        await session.execute(select(ShopLogo).where(ShopLogo.token == token))
    ).scalar_one_or_none()
    if logo is None:
        raise HTTPException(status_code=404, detail="image not found")
    return _image_response(logo.data, logo.mime)
