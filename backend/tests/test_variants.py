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
async def test_variant_keeps_its_own_title_and_description(db):
    """Вариациями продают не только цвета, но и комплектации: у них расходится
    и название, и текст. Покупателю они обязаны доехать до страницы товара."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c,
            bot_id,
            [
                variant(5, 3, "Красный", title="Футболка красная", description="Хлопок"),
                variant(7, 2, "Синий", title="Футболка синяя"),
            ],
        )
        assert [v["title"] for v in body["variants"]] == [
            "Футболка красная",
            "Футболка синяя",
        ]
        assert [v["description"] for v in body["variants"]] == ["Хлопок", None]

        shop = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        shown = shop.json()["products"][0]["variants"]
    assert [v["title"] for v in shown] == ["Футболка красная", "Футболка синяя"]
    assert shown[0]["description"] == "Хлопок"


@pytest.mark.asyncio
async def test_variants_without_titles_stay_empty_not_broken(db):
    """Вариации, созданные до появления этих колонок, названия не имеют —
    витрина обязана продолжать работать и показывать товарное."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(c, bot_id, [variant(5, 1), variant(7, 1, "Синий")])
        shop = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
    assert [v["title"] for v in body["variants"]] == [None, None]
    assert shop.json()["products"][0]["title"] == "Футболка"


@pytest.mark.asyncio
async def test_product_without_variants_keeps_its_own_compare_price(db):
    """Скидка у обычного товара: заводить ради зачёркнутой цены вариацию —
    бессмысленно, поэтому compare_at_price есть и у самого товара."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={
                "type": "physical",
                "title": "Кружка",
                "price": "7",
                "compare_at_price": "10",
                "variants": [],
            },
        )
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["compare_at_price"]) == Decimal("10")

        # покупатель обязан её видеть — иначе зачёркивать нечего
        shop = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        assert Decimal(shop.json()["products"][0]["compare_at_price"]) == Decimal("10")


@pytest.mark.asyncio
async def test_product_compare_price_must_be_a_discount(db):
    """То же правило, что и у вариации: зачёркнутое число выше текущего."""
    bot_id = await setup_shop(db)
    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={
                "type": "physical",
                "title": "Кружка",
                "price": "10",
                "compare_at_price": "10",
            },
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_variants_clear_the_products_own_compare_price(db):
    """Витринная цена товара с вариациями — минимум по ним («от 500»).
    Зачеркнуть рядом с ней своё старое число значило бы соврать про скидку."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c,
            bot_id,
            [variant(5, 3, "Красный"), variant(7, 2, "Синий")],
            price="10",
        )
        assert body["compare_at_price"] is None

        # и при добавлении вариаций к товару, у которого скидка уже была
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={
                "type": "physical",
                "title": "Кружка",
                "price": "7",
                "compare_at_price": "10",
            },
        )
        product_id = r.json()["id"]
        r = await c.put(
            f"/api/seller/bots/{bot_id}/products/{product_id}",
            headers=seller_headers(),
            json={
                "type": "physical",
                "title": "Кружка",
                "price": "7",
                "compare_at_price": "10",
                "variants": [variant(5, 1, "Малая"), variant(9, 1, "Большая")],
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["compare_at_price"] is None


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
async def test_order_line_is_named_by_the_bought_variant(db):
    """Товарное название принадлежит первой вариации: без снимка своего имени
    строка заказа для второй называла бы чужой вариант."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c,
            bot_id,
            [
                variant(5, 3, "Красный", title="Футболка красная"),
                variant(7, 3, "Синий", title="Футболка синяя"),
            ],
        )
        blue = body["variants"][1]["id"]
        created = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": body["id"], "variant_id": blue, "qty": 1}],
                "delivery": {"address": "Тверская 1"},
            },
        )
        assert created.status_code == 200, created.text
        line = created.json()["items"][0]
        assert line["title"] == "Футболка синяя"
        assert line["variant_label"] == "Синий"

        mine = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        shown = mine.json()[0]["items"][0]
        assert shown["title"] == "Футболка синяя"
        assert shown["variant_label"] == "Синий"

    # рабочий список продавца начинается с оплаты — доводим заказ до неё
    async with db() as session:
        order = await session.get(Order, created.json()["id"])
        order.status = "paid"
        await session.commit()

    async with client() as c:
        seller = await c.get(f"/api/seller/bots/{bot_id}/orders", headers=seller_headers())
        for_seller = seller.json()[0]["items"][0]
    assert for_seller["title"] == "Футболка синяя"
    assert for_seller["variant_label"] == "Синий"


@pytest.mark.asyncio
async def test_order_line_survives_renaming_the_variant(db):
    """Снимок, а не ссылка: продавец переименует вариацию, а в старом заказе
    должно остаться то, за что человек заплатил."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(
            c, bot_id, [variant(5, 3, "Красный", title="Футболка красная")]
        )
        first = body["variants"][0]["id"]
        await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [{"product_id": body["id"], "variant_id": first, "qty": 1}],
                "delivery": {"address": "Тверская 1"},
            },
        )
        await c.put(
            f"/api/seller/bots/{bot_id}/products/{body['id']}",
            headers=seller_headers(),
            json={
                "type": "physical",
                "title": "Футболка",
                "price": "5",
                "variants": [
                    {
                        "id": first,
                        "attributes": {"Цвет": "Бордовый"},
                        "title": "Футболка бордовая",
                        "price": "5",
                        "stock": 3,
                    }
                ],
            },
        )
        mine = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        shown = mine.json()[0]["items"][0]
    assert shown["title"] == "Футболка красная"
    assert shown["variant_label"] == "Красный"


@pytest.mark.asyncio
async def test_order_line_without_variant_title_falls_back_to_product(db):
    """Заказы, созданные до появления колонки, называются товарным."""
    bot_id = await setup_shop(db)
    async with client() as c:
        body = await make_product(c, bot_id, [variant(5, 3, "Красный")])
        await c.post(
            f"/api/store/{bot_id}/orders",
            headers=buyer_headers(),
            json={
                "items": [
                    {"product_id": body["id"], "variant_id": body["variants"][0]["id"], "qty": 1}
                ],
                "delivery": {"address": "Тверская 1"},
            },
        )
        mine = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
    assert mine.json()[0]["items"][0]["title"] == "Футболка"


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
