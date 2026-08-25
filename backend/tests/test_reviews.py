"""Отзывы о товарах: только за доставленный заказ, upsert по паре
(заказ, товар), рейтинг на витрине, анонимность наружу."""

import pytest
from unittest.mock import AsyncMock, patch

from tests.test_api import BUYER, buyer_headers, client, seller_headers, setup_shop
from tests.test_fulfillment import paid_physical_order


@pytest.mark.asyncio
async def test_product_reviews_flow(db):
    bot_id, order_id = await paid_physical_order(db)

    async with client() as c:
        # единственный товар заказа + посторонний товар для проверки отказа
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        pid = r.json()["products"][0]["id"]
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Посторонний", "price": "1"},
        )
        stranger_pid = r.json()["id"]

        # заказ ещё не доставлен — оценивать рано
        r = await c.post(
            f"/api/store/{bot_id}/orders/{order_id}/reviews",
            headers=buyer_headers(),
            json={"items": [{"product_id": pid, "rating": 5}]},
        )
        assert r.status_code == 400

    # продавец отправляет заказ -> покупателю уходит пуш с напоминанием оценить
    with patch("app.payments.service._notify", new=AsyncMock()) as notify_mock:
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"note": "Выдано на кассе"},
            )
            assert r.status_code == 200, r.text
            push_text = notify_mock.call_args.args[2]
            assert "Оцени покупки" in push_text

            # чужой товар в payload не проходит целиком
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={
                    "items": [
                        {"product_id": pid, "rating": 5},
                        {"product_id": stranger_pid, "rating": 1},
                    ]
                },
            )
            assert r.status_code == 400

            # оценка чужого/несуществующего заказа не выдаёт даже факта существования
            r = await c.post(
                f"/api/store/{bot_id}/orders/999999/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 5}]},
            )
            assert r.status_code == 403

            # доставка состоялась — оставляем отзыв
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 5, "body": "Отлично"}]},
            )
            assert r.status_code == 200, r.text
            review = r.json()[0]
            assert review["rating"] == 5
            assert review["created_at"]

            # повторная отправка правит оценку, а не плодит вторую
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 4}]},
            )
            assert r.status_code == 200, r.text

            # витрина: среднее и количество
            r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
            product = next(p for p in r.json()["products"] if p["id"] == pid)
            assert product["reviews_count"] == 1
            assert float(product["avg_rating"]) == pytest.approx(4.0)
            stranger = next(p for p in r.json()["products"] if p["id"] == stranger_pid)
            assert stranger["avg_rating"] is None and stranger["reviews_count"] == 0

            # список отзывов товара: без автора, свежая версия оценки
            r = await c.get(
                f"/api/store/{bot_id}/products/{pid}/reviews", headers=buyer_headers()
            )
            reviews = r.json()
            assert len(reviews) == 1
            assert reviews[0]["rating"] == 4 and reviews[0]["body"] is None
            assert "petya" not in str(reviews) and BUYER["username"] not in str(reviews)

            # покупателю видно, что позиция оценена
            r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
            items = r.json()[0]["items"]
            assert [i["reviewed"] for i in items if i["product_id"] == pid] == [True]

            # продавец видит отзывы со названиями товаров и без автора
            r = await c.get(f"/api/seller/bots/{bot_id}/reviews", headers=seller_headers())
            seller_reviews = r.json()
            assert len(seller_reviews) == 1
            assert seller_reviews[0]["product_title"] == "Кроссовки"
            assert seller_reviews[0]["rating"] == 4
            assert "petya" not in str(seller_reviews)

            # чужой товар магазина отзывов не имеет
            r = await c.get(
                f"/api/store/{bot_id}/products/{stranger_pid}/reviews",
                headers=buyer_headers(),
            )
            assert r.status_code == 200 and r.json() == []
