"""Отзывы о товарах: только за доставленный заказ, upsert по паре
(заказ, товар), рейтинг на витрине, псевдоним автора вместо личности,
удаление своего отзыва, ответ продавца, пуш продавцу о новом отзыве."""

import pytest
from unittest.mock import AsyncMock, patch

from tests.test_api import (
    BUYER,
    SELLER_BOT_TOKEN,
    buyer_headers,
    client,
    init_data_for,
    seller_headers,
    setup_shop,
)
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
                json={"value": "Выдано на кассе"},
            )
            # «Доставлен» ставит покупатель — оценивать можно только после
            await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/received",
                headers=buyer_headers(),
            )
            assert r.status_code == 200, r.text
            push_text = notify_mock.call_args.args[2]
            # после отправки зовём отметить получение, оценка — уже там
            assert "отметь в «Моих покупках»" in push_text

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
            # автор — Telegram-имя покупателя; юзернейм по-прежнему не светится
            author = review["author_name"]
            assert author == "Петя"
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

            # рейтинг магазина на шапке складывается из всех его отзывов,
            # продажи считаются по оплаченным заказам
            shop_body = r.json()
            assert float(shop_body["rating"]) == pytest.approx(4.0)
            assert shop_body["sales_count"] == 1

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
            assert seller_reviews[0]["order_id"] == order_id
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
async def test_review_author_falls_back_to_pseudonym_without_name(db):
    """Покупатель без first_name в Telegram — остаётся случайный псевдоним."""
    bot_id = await setup_shop(db)
    anon_headers = {
        "X-Init-Data": init_data_for({"id": 888, "username": "noname"}, SELLER_BOT_TOKEN)
    }

    async with client() as c:
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Кружка", "price": "7"},
        )
        pid = r.json()["id"]
        r = await c.post(
            f"/api/store/{bot_id}/orders",
            headers=anon_headers,
            json={"delivery": {"name": "Аня", "phone": "+79990001122", "address": "Тверская 1"}, "items": [{"product_id": pid, "qty": 1}]},
        )
        order_id = r.json()["id"]

    from app.db import get_session
    from app.models import Order

    async with get_session() as session:
        order = await session.get(Order, order_id)
        order.invoice_id = 700200
        await session.commit()

    from tests.test_payments import patched_notifications

    p1, p2 = patched_notifications()
    with p1, p2:
        from app.payments.service import handle_invoice_paid

        assert await handle_invoice_paid(700200, None)

    with patch("app.payments.service._notify", new=AsyncMock()):
        async with client() as c:
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"value": "Выдано"},
            )
            # подтверждает получение сам покупатель этого заказа
            await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/received", headers=anon_headers
            )
            assert r.status_code == 200, r.text

            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=anon_headers,
                json={"items": [{"product_id": pid, "rating": 3}]},
            )
            assert r.status_code == 200, r.text
            body = str(r.json())
            # вместо пустого имени — псевдоним вида «Анна К.», юзернейм не светится
            author = r.json()[0]["author_name"]
            assert author and author.endswith(".")
            assert "noname" not in body


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
                json={"value": "Выдано"},
            )
            # «Доставлен» ставит покупатель — оценивать можно только после
            await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/received",
                headers=buyer_headers(),
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

        # рейтинг товара обнулился; вместе с ним пропал и магазинный
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        body = r.json()
        product = next(p for p in body["products"] if p["id"] == pid)
        assert product["reviews_count"] == 0 and product["avg_rating"] is None
        assert body["rating"] is None
        assert body["sales_count"] == 1  # продажа от отзыва не зависит

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
                json={"value": "Выдано"},
            )
            # «Доставлен» ставит покупатель — оценивать можно только после
            await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/received",
                headers=buyer_headers(),
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


async def _delivered_order_with_product(db):
    """Доставленный заказ + id единственного товара (отзыв ещё не оставлен)."""
    bot_id, order_id = await paid_physical_order(db)
    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        pid = r.json()["products"][0]["id"]
        with patch("app.payments.service._notify", new=AsyncMock()):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/orders/{order_id}/fulfill",
                headers=seller_headers(),
                json={"value": "Выдано"},
            )
            # «Доставлен» ставит покупатель — оценивать можно только после
            await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/received",
                headers=buyer_headers(),
            )
            assert r.status_code == 200, r.text
    return bot_id, order_id, pid


@pytest.mark.asyncio
async def test_low_rating_review_waits_for_moderation(db):
    """Оценка ниже порога (4) скрыта от витрины до одобрения продавца."""
    from app.config import get_settings

    assert get_settings().review_auto_publish_min == 4
    bot_id, order_id, pid = await _delivered_order_with_product(db)

    async with client() as c:
        with patch("app.api.store.notify_new_review", new=AsyncMock()):
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 3, "body": "не то"}]},
            )
        assert r.status_code == 200, r.text
        review = r.json()[0]
        assert review["status"] == "pending"

        # из публичного списка и из рейтингов ожидающий не виден
        r = await c.get(
            f"/api/store/{bot_id}/products/{pid}/reviews", headers=buyer_headers()
        )
        assert r.json() == []
        r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
        body = r.json()
        product = next(p for p in body["products"] if p["id"] == pid)
        assert product["reviews_count"] == 0 and product["avg_rating"] is None
        assert body["rating"] is None

        # покупатель видит свой отзыв со статусом «на проверке»
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        mine = r.json()[0]["items"][0]["my_review"]
        assert mine["rating"] == 3 and mine["status"] == "pending"

        # продавцу отзыв виден — в статусе на проверке
        r = await c.get(f"/api/seller/bots/{bot_id}/reviews", headers=seller_headers())
        seller_review = r.json()[0]
        assert seller_review["status"] == "pending"
        assert seller_review["moderated_at"] is None


@pytest.mark.asyncio
async def test_edit_rating_recomputes_status(db):
    """Правка оценки пересчитывает статус по порогу в обе стороны."""
    bot_id, order_id, pid = await _delivered_order_with_product(db)

    async with client() as c:
        with patch("app.api.store.notify_new_review", new=AsyncMock()):

            async def _post(rating):
                return await c.post(
                    f"/api/store/{bot_id}/orders/{order_id}/reviews",
                    headers=buyer_headers(),
                    json={"items": [{"product_id": pid, "rating": rating}]},
                )

            # 5 -> опубликован сразу
            r = await _post(5)
            assert r.json()[0]["status"] == "published"

            # 5 -> 2: уходит на проверку, из витрины исчезает
            r = await _post(2)
            assert r.json()[0]["status"] == "pending"
            r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
            product = next(p for p in r.json()["products"] if p["id"] == pid)
            assert product["reviews_count"] == 0

            # 2 -> 5: возвращается в публикацию
            r = await _post(5)
            assert r.json()[0]["status"] == "published"
            r = await c.get(f"/api/store/{bot_id}", headers=buyer_headers())
            product = next(p for p in r.json()["products"] if p["id"] == pid)
            assert product["reviews_count"] == 1


@pytest.mark.asyncio
async def test_seller_approve_reject(db):
    bot_id, order_id, pid = await _delivered_order_with_product(db)

    async with client() as c:
        with patch("app.api.store.notify_new_review", new=AsyncMock()):
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 2}]},
            )
        review_id = r.json()[0]["id"]

        # чужой магазин и несуществующий отзыв не различаются — 404
        r = await c.post(
            f"/api/seller/bots/{bot_id}/reviews/999999/approve", headers=seller_headers()
        )
        assert r.status_code == 404
        r = await c.post(
            f"/api/seller/bots/{bot_id}/reviews/999999/reject", headers=seller_headers()
        )
        assert r.status_code == 404

        # одобрение публикует: из рейтингов и публичного списка
        r = await c.post(
            f"/api/seller/bots/{bot_id}/reviews/{review_id}/approve",
            headers=seller_headers(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "published" and r.json()["moderated_at"]
        r = await c.get(
            f"/api/store/{bot_id}/products/{pid}/reviews", headers=buyer_headers()
        )
        assert [x["rating"] for x in r.json()] == [2]

        # повторное одобрение идемпотентно
        r = await c.post(
            f"/api/seller/bots/{bot_id}/reviews/{review_id}/approve",
            headers=seller_headers(),
        )
        assert r.status_code == 200 and r.json()["status"] == "published"

        # отклонение прячет отзыв; повторное отклонение тоже идемпотентно
        for _ in range(2):
            r = await c.post(
                f"/api/seller/bots/{bot_id}/reviews/{review_id}/reject",
                headers=seller_headers(),
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "rejected"
        r = await c.get(
            f"/api/store/{bot_id}/products/{pid}/reviews", headers=buyer_headers()
        )
        assert r.json() == []

        # правка отклонённого не публикует его обратно, даже с высокой оценкой
        with patch("app.api.store.notify_new_review", new=AsyncMock()):
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 5}]},
            )
        assert r.json()[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_auto_publish_stale_reviews(db):
    """Джоб публикует ожидающие старше review_moderation_days, свежие не трогает."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    from app.config import get_settings
    from app.db import get_session
    from app.models import ProductReview
    from app.services.reviews import auto_publish_stale_reviews

    days = get_settings().review_moderation_days
    bot_id, order_id, pid = await _delivered_order_with_product(db)

    async with client() as c:
        with patch("app.api.store.notify_new_review", new=AsyncMock()):
            r = await c.post(
                f"/api/store/{bot_id}/orders/{order_id}/reviews",
                headers=buyer_headers(),
                json={"items": [{"product_id": pid, "rating": 3}]},
            )
        review_id = r.json()[0]["id"]

        # второй товар — свежий ожидающий отзыв на него, прямым инсёртом
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            headers=seller_headers(),
            json={"type": "physical", "title": "Шапка", "price": "10"},
        )
        pid2 = r.json()["id"]

    async with get_session() as session:
        review = await session.get(ProductReview, review_id)
        fresh = ProductReview(
            bot_id=review.bot_id,
            product_id=pid2,
            order_id=review.order_id,
            customer_id=review.customer_id,
            rating=1,
            author_name="Кто-то Ч.",
            status="pending",
        )
        session.add(fresh)
        await session.flush()
        fresh_id = fresh.id
        await session.execute(
            update(ProductReview)
            .where(ProductReview.id == review_id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=days + 1))
        )
        await session.commit()

    # один устаревший — публикуется, свежий остаётся на месте
    assert await auto_publish_stale_reviews() == 1

    async with client() as c:
        r = await c.get(f"/api/store/{bot_id}/orders/my", headers=buyer_headers())
        mine = r.json()[0]["items"][0]["my_review"]
        assert mine["status"] == "published"

    async with get_session() as session:
        assert (await session.get(ProductReview, fresh_id)).status == "pending"

    # повторный проход никого не находит
    assert await auto_publish_stale_reviews() == 0
