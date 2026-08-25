"""Отзывы о товарах: только за доставленный заказ, upsert по паре
(заказ, товар), рейтинг на витрине, псевдоним автора вместо личности,
удаление своего отзыва, ответ продавца, пуш продавцу о новом отзыве."""

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
    with (
        patch("app.payments.service._notify", new=AsyncMock()) as notify_mock,
        patch("app.api.store.notify_new_review", new=AsyncMock()) as review_push,
    ):
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
            # у отзыва есть псевдоним автора, личность по-прежнему не светится
            author = review["author_name"]
            assert author and len(author) > 3
            assert "petya" not in str(review) and BUYER["username"] not in str(review)
            # пуш продавцу — ровно один, о создании
            review_push.assert_awaited_once()

            # повторная отправка правит оценку, а не плодит вторую;
            # псевдоним при правке не меняется и пуша нет
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 4}]},
            )
            assert r.status_code == 200, r.text
            assert r.json()[0]["author_name"] == author
            review_push.assert_awaited_once()

            # витрина: среднее и количество
            r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
            product = next(p for p in r.json()["products"] if p["id"] == pid)
            assert product["reviews_count"] == 1
            assert float(product["avg_rating"]) == pytest.approx(4.0)
            stranger = next(p for p in r.json()["products"] if p["id"] == stranger_pid)
            assert stranger["avg_rating"] is None and stranger["reviews_count"] == 0

            # список отзывов товара: без личности, свежая версия оценки
            r = await c.get(
                f"/api/store/{bot_id}/products/{pid}/reviews", headers=buyer_headers()
            )
            reviews = r.json()
            assert len(reviews) == 1
            assert reviews[0]["rating"] == 4 and reviews[0]["body"] is None
            assert reviews[0]["author_name"] == author
            assert reviews[0]["reply_body"] is None and reviews[0]["reply_at"] is None
            assert "petya" not in str(reviews) and BUYER["username"] not in str(reviews)

            # покупателю виден и флаг, и сам отзыв — форма правки откроется заполненной
            r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
            items = r.json()[0]["items"]
            mine = next(i for i in items if i["product_id"] == pid)
            assert mine["reviewed"] is True
            assert mine["my_review"]["rating"] == 4 and mine["my_review"]["body"] is None

            # продавец видит отзывы с названиями товаров и без личности
            r = await c.get(f"/api/seller/bots/{bot_id}/reviews", headers=seller_headers())
            seller_reviews = r.json()
            assert len(seller_reviews) == 1
            assert seller_reviews[0]["product_title"] == "Кроссовки"
            assert seller_reviews[0]["rating"] == 4
            assert seller_reviews[0]["author_name"] == author
            assert "petya" not in str(seller_reviews)

            # чужой товар магазина отзывов не имеет
            r = await c.get(
                f"/api/store/{bot_id}/products/{stranger_pid}/reviews",
                headers=buyer_headers(),
            )
            assert r.status_code == 200 and r.json() == []


@pytest.mark.asyncio
async def test_delete_own_review_recalculates_rating(db):
    bot_id, order_id = await paid_physical_order(db)

    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        pid = r.json()["products"][0]["id"]

        with patch("app.payments.service._notify", new=AsyncMock()):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"note": "Выдано"},
            )
            assert r.status_code == 200, r.text

        r = await c.post(
            f"/api/store/{bot_id}/orders/{order_id}/reviews",
            headers=buyer_headers(),
            json={"items": [{"product_id": pid, "rating": 2, "body": "не очень"}]},
        )
        assert r.status_code == 200, r.text

        # удаление своего отзыва
        r = await c.delete(
            f"/api/store/{bot_id}/orders/{order_id}/reviews/{pid}",
            headers=buyer_headers(),
        )
        assert r.status_code == 200, r.text

        # рейтинг товара обнулился
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        product = next(p for p in r.json()["products"] if p["id"] == pid)
        assert product["reviews_count"] == 0 and product["avg_rating"] is None

        # второго раза нет
        r = await c.delete(
            f"/api/store/{bot_id}/orders/{order_id}/reviews/{pid}",
            headers=buyer_headers(),
        )
        assert r.status_code == 404

        # чужой заказ удалению не подлежит — даже факт отзыва не выдаётся
        r = await c.delete(
            f"/api/store/{bot_id}/orders/999999/reviews/{pid}",
            headers=buyer_headers(),
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_seller_reply_visible_to_buyers(db):
    bot_id, order_id = await paid_physical_order(db)

    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        pid = r.json()["products"][0]["id"]

        with patch("app.payments.service._notify", new=AsyncMock()):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"note": "Выдано"},
            )
            assert r.status_code == 200, r.text

        r = await c.post(
            f"/api/store/{bot_id}/orders/{order_id}/reviews",
            headers=buyer_headers(),
            json={"items": [{"product_id": pid, "rating": 5, "body": "Супер"}]},
        )
        assert r.status_code == 200, r.text
        review_id = r.json()[0]["id"]

        # несуществующий отзыв -> 404, независимо от магазина
        r = await c.post(
            f"/api/seller/bots/{bot_id}/reviews/999999/reply",
            headers=seller_headers(),
            json={"body": "Спасибо!"},
        )
        assert r.status_code == 404

        # продавец отвечает
        r = await c.post(
            f"/api/seller/bots/{bot_id}/reviews/{review_id}/reply",
            headers=seller_headers(),
            json={"body": "Спасибо за покупку!"},
        )
        assert r.status_code == 200, r.text
        replied = r.json()
        assert replied["reply_body"] == "Спасибо за покупку!"
        assert replied["reply_at"]

        # покупатель видит ответ вместе с псевдонимом автора
        r = await c.get(
            f"/api/store/{bot_id}/products/{pid}/reviews", headers=buyer_headers()
        )
        public = r.json()[0]
        assert public["reply_body"] == "Спасибо за покупку!"
        assert public["reply_at"]
        assert public["author_name"]

        # повторный ответ перезаписывает
        r = await c.post(
            f"/api/seller/bots/{bot_id}/reviews/{review_id}/reply",
            headers=seller_headers(),
            json={"body": "И правда спасибо!"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["reply_body"] == "И правда спасибо!"

        # в списке продавца ответ тоже есть
        r = await c.get(f"/api/seller/bots/{bot_id}/reviews", headers=seller_headers())
        assert r.json()[0]["reply_body"] == "И правда спасибо!"
