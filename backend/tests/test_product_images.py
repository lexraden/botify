"""Фото товаров: загрузка с устройства, проверка содержимого, изоляция по магазину."""

import os

import pytest

from app.services.images import MAX_IMAGE_BYTES, sniff_image_mime
from tests.test_api import buyer_headers, client, init_data_for, seller_headers, setup_shop
from tests.test_bot_connect import make_seller

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"JFIF" + b"0" * 64


async def _upload(bot_id: int, data: bytes, headers=None):
    async with client() as c:
        return await c.post(
            f"/api/seller/bots/{bot_id}/product-image",
            headers=headers if headers is not None else seller_headers(),
            content=data,
        )


def test_sniffer_recognises_whitelisted_types_only():
    assert sniff_image_mime(PNG_BYTES) == "image/png"
    assert sniff_image_mime(JPEG_BYTES) == "image/jpeg"
    assert sniff_image_mime(b"GIF89a" + b"0" * 32) == "image/gif"
    # WebP: RIFF....WEBP
    assert sniff_image_mime(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff_image_mime(b"<html>not an image</html>") is None
    assert sniff_image_mime(b"") is None


@pytest.mark.asyncio
async def test_upload_valid_image_and_serve(db):
    """Валидная картинка сохраняется, отдаётся без авторизации и вешается на товар."""
    bot_id = await setup_shop(db)

    r = await _upload(bot_id, PNG_BYTES)
    assert r.status_code == 200, r.text
    body = r.json()
    image_url = body["url"]
    assert image_url == f"/api/images/{body['id']}"

    async with client() as c:
        served = await c.get(image_url)  # покупателю авторизация не нужна
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("image/png")
        assert served.content == PNG_BYTES
        assert served.headers["x-content-type-options"] == "nosniff"

        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "image_url": image_url},
        )
        assert r.status_code == 200
        assert r.json()["image_url"] == image_url

        # товар с картинкой виден на витрине — покупатель получит тот же путь
        store = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        product = store.json()["products"][0]
        assert product["image_url"] == image_url


@pytest.mark.asyncio
async def test_upload_rejects_non_image_despite_client_hints(db):
    """Текст под видом PNG (и content-type совран) отвергается по содержимому."""
    bot_id = await setup_shop(db)
    fake = b"<html>not an image</html>"
    headers = {**seller_headers(), "Content-Type": "image/png"}
    r = await _upload(bot_id, fake, headers=headers)
    assert r.status_code == 400
    assert "JPEG" in r.json()["detail"]


@pytest.mark.asyncio
async def test_magic_beats_declared_type(db):
    """Настоящий JPEG без расширения и с нейтральным content-type принимается."""
    bot_id = await setup_shop(db)
    headers = {**seller_headers(), "Content-Type": "application/octet-stream"}
    r = await _upload(bot_id, JPEG_BYTES, headers=headers)
    assert r.status_code == 200
    async with client() as c:
        served = await c.get(r.json()["url"])
        assert served.headers["content-type"].startswith("image/jpeg")


@pytest.mark.asyncio
async def test_oversized_upload_rejected(db):
    """Больше 5 МБ нельзя, даже если содержимое — валидная картинка."""
    bot_id = await setup_shop(db)
    data = PNG_BYTES + b"0" * MAX_IMAGE_BYTES  # чуть больше лимита
    r = await _upload(bot_id, data)
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_empty_upload_rejected(db):
    bot_id = await setup_shop(db)
    r = await _upload(bot_id, b"")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_missing_image_is_404(db):
    async with client() as c:
        r = await c.get("/api/images/999999")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_replace_and_remove_product_image(db):
    """Замена: товар начинает ссылаться на новую картинку; удаление: ссылка пуста."""
    bot_id = await setup_shop(db)
    first = (await _upload(bot_id, PNG_BYTES)).json()["url"]
    second = (await _upload(bot_id, JPEG_BYTES)).json()["url"]

    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "image_url": first},
        )
        pid = r.json()["id"]

        r = await c.put(
            f"/api/seller/bots/{bot_id}/products/{pid}",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "image_url": second},
        )
        assert r.status_code == 200
        assert r.json()["image_url"] == second

        r = await c.put(
            f"/api/seller/bots/{bot_id}/products/{pid}",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "10", "image_url": None},
        )
        assert r.status_code == 200
        assert r.json()["image_url"] is None


@pytest.mark.asyncio
async def test_upload_requires_shop_owner(db):
    """Чужой магазин недоступен: незнакомец без initData — 401,
    зарегистрированный чужой продавец — 404 (магазин «не существует»)."""
    bot_id = await setup_shop(db)

    r = await _upload(bot_id, PNG_BYTES, headers={})
    assert r.status_code == 401

    await make_seller(db, telegram_id=222)  # зарегистрированный чужой продавец
    stranger = {"X-Init-Data": init_data_for({"id": 222}, os.environ["HUB_BOT_TOKEN"])}
    r = await _upload(bot_id, PNG_BYTES, headers=stranger)
    assert r.status_code == 404
