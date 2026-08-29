"""Вариации товара: цена, остаток и фото у каждой свои.

Главное, что здесь проверяется, — не форма API, а деньги: за какую вариацию
человек заплатил и с какой строки списался остаток. Ошибка здесь означает,
что покупатель платит за один размер, а продавец отгружает другой.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Order, OrderItem, Product, ProductVariant
from app.services.variants import variant_label
from tests.test_api import buyer_headers, client, seller_headers, setup_shop


def variant(price, stock=None, color="Красный", **extra):
    return {
        "price": str(price),
        "stock": stock,
        "attributes": {"Цвет": color},
        **extra,
    }


async def make_product(c, bot_id, variants, price="10", stock=None):
    r = await c.post(
        f"/api/seller/bots/{bot_id}/products",
        headers=seller_headers(),
        json={
            "type": "physical",
            "title": "Футболка",
            "price": price,
            "stock": stock,
            "variants": variants,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------
# Сохранение набора вариаций
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_variants_saved_with_product(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c, bot_id, [variant(5, 3, "Красный"), variant(7, 2, "Синий")]
        )

    assert len(body["variants"]) == 2
    assert [v["attributes"]["Цвет"] for v in body["variants"]] == ["Красный", "Синий"]
    # у каждой свой id — по нему покупатель и выбирает
    assert len({v["id"] for v in body["variants"]}) == 2


@pytest.mark.asyncio
async def test_product_price_and_stock_come_from_variants(db):
    """Витрина и статистика читают товар как раньше — значит его цена и
    остаток обязаны отражать вариации: «от 5» и суммарный остаток."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c, bot_id, [variant(9, 3, "Красный"), variant(5, 2, "Синий")], price="100"
        )

    assert Decimal(body["price"]) == Decimal("5")  # минимальная, а не присланная
    assert body["stock"] == 5


@pytest.mark.asyncio
async def test_unlimited_variant_makes_product_unlimited(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c, bot_id, [variant(5, 3, "Красный"), variant(5, None, "Синий")]
        )
    assert body["stock"] is None


@pytest.mark.asyncio
async def test_variants_only_for_physical(db):
    """У услуги нет ни цвета, ни размера — цена живёт на самом товаре."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={
                "type": "service",
                "title": "Консультация",
                "price": "10",
                "variants": [variant(5, 1)],
            },
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_compare_at_price_must_be_a_discount(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={
                "type": "physical",
                "title": "Футболка",
                "price": "10",
                "variants": [variant(10, 1, compare_at_price="9")],
            },
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_editing_updates_adds_and_removes(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(c, bot_id, [variant(5, 3, "Красный"), variant(7, 2, "Синий")])
        keep, drop = body["variants"]

        r = await c.put(
            f"/api/seller/bots/{bot_id}/products/{body['id']}",
            headers=seller_headers(),
            json={
                "type": "physical",
                "title": "Футболка",
                "price": "10",
                "variants": [
                    {**variant(6, 4, "Красный"), "id": keep["id"]},
                    variant(8, 1, "Зелёный"),
                ],
            },
        )
    assert r.status_code == 200, r.text
    out = r.json()
    ids = {v["id"] for v in out["variants"]}
    assert keep["id"] in ids  # обновлена
    assert drop["id"] not in ids  # убрана
    assert len(ids) == 2
    assert Decimal(next(v["price"] for v in out["variants"] if v["id"] == keep["id"])) == Decimal("6")


@pytest.mark.asyncio
async def test_foreign_image_url_is_rejected(db):
    """Ссылка не из нашего загрузчика попала бы в <img src> на витрине."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c,
            bot_id,
            [variant(5, 1, images=["https://evil.example/x.png", "/api/images/abc"])],
        )
    assert body["variants"][0]["images"] == ["/api/images/abc"]


# --------------------------------------------------------------------------
# Покупка вариации
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buyer_must_choose_a_variant(db):
    """Без выбора непонятно, за какой размер человек заплатил."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(c, bot_id, [variant(5, 3), variant(7, 2, "Синий")])
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": body["id"], "qty": 1}],
                "delivery": {"address": "Тверская 1"},
            },
        )
    assert r.status_code == 400
    assert "variant_required" in r.text


@pytest.mark.asyncio
async def test_variant_of_another_product_is_refused(db):
    """Иначе можно было бы прислать id дешёвой вариации к дорогому товару."""
    bot_id = await setup_shop(db)
    async with client() as c:
        cheap = await make_product(c, bot_id, [variant(1, 5, "Дешёвый")])
        pricey = await make_product(c, bot_id, [variant(500, 5, "Дорогой")])
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [
                    {
                        "product_id": pricey["id"],
                        "variant_id": cheap["variants"][0]["id"],
                        "qty": 1,
                    }
                ],
                "delivery": {"address": "Тверская 1"},
            },
        )
    assert r.status_code == 400
    assert "variant not available" in r.text


@pytest.mark.asyncio
async def test_order_is_priced_by_the_chosen_variant(db):
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(c, bot_id, [variant(5, 3, "Красный"), variant(11, 2, "Синий")])
        blue = body["variants"][1]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": body["id"], "variant_id": blue["id"], "qty": 2}],
                "delivery": {"address": "Тверская 1"},
            },
        )
    assert r.status_code == 200, r.text
    # 11 * 2, а не витринная «от 5»
    assert Decimal(r.json()["total"]) == Decimal("22")

    async with db() as session:
        item = (await session.execute(select(OrderItem))).scalars().one()
        assert item.variant_id == blue["id"]
        # снимок свойств: продавец переименует размеры, заказ не изменится
        assert item.variant_label == "Синий"


@pytest.mark.asyncio
async def test_stock_checked_per_variant_not_per_product(db):
    """Суммарного остатка товара хватает, а нужного размера — нет."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(c, bot_id, [variant(5, 1, "Красный"), variant(5, 9, "Синий")])
        red = body["variants"][0]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": body["id"], "variant_id": red["id"], "qty": 3}],
                "delivery": {"address": "Тверская 1"},
            },
        )
    assert r.status_code == 400
    assert "insufficient stock" in r.text


@pytest.mark.asyncio
async def test_payment_decrements_the_bought_variant(db):
    """Самое важное: списывается тот размер, который купили."""
    from app.payments.service import handle_invoice_paid
    from tests.test_payments import patched_notifications

    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(c, bot_id, [variant(5, 4, "Красный"), variant(5, 4, "Синий")])
        red, blue = body["variants"]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": body["id"], "variant_id": blue["id"], "qty": 3}],
                "delivery": {"address": "Тверская 1"},
            },
        )
        order_id = r.json()["id"]

    async with db() as session:
        order = await session.get(Order, order_id)
        order.invoice_id = 771001
        await session.commit()

    p1, p2 = patched_notifications()
    with p1, p2:
        assert await handle_invoice_paid(771001, None) is True

    async with db() as session:
        assert (await session.get(ProductVariant, blue["id"])).stock == 1  # 4 - 3
        assert (await session.get(ProductVariant, red["id"])).stock == 4  # не тронут
        # витринный остаток товара при этом не трогаем: он пересчитывается
        # при сохранении товара, а не при каждой продаже
        assert (await session.get(Product, body["id"])).stock == 8


def test_variant_label_joins_attributes():
    assert variant_label({"Цвет": "Красный", "Размер": "M"}) == "Красный · M"
    assert variant_label(None) == ""
