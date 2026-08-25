"""API витрины: покупатель внутри seller-бота. Всё отфильтровано по продавцу бота."""

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BuyerContext, get_buyer
from app.models import (
    BotAvatar,
    Customer,
    Order,
    OrderChat,
    OrderItem,
    Product,
    ProductReview,
    Seller,
    ShopEvent,
)
from app.services.bot_avatars import refresh_bot_avatar
from app.services.reviews import notify_new_review, random_author_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/store/{bot_id}")


class ProductOut(BaseModel):
    id: int
    type: str
    title: str
    description: str | None
    image_url: str | None
    price: Decimal
    currency: str
    # остаток; None — не ограничен, 0 — «нет в наличии»
    stock: int | None
    # рейтинг: среднее по отзывам покупателей; нет отзывов — None и ноль
    avg_rating: float | None = None
    reviews_count: int = 0

    model_config = {"from_attributes": True}


class ShopOut(BaseModel):
    shop_name: str
    # фото бота из Telegram — логотип магазина в шапке витрины; None — нет фото
    shop_avatar_url: str | None = None
    products: list[ProductOut]


class CartItemIn(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=99)


class OrderIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    comment: str | None = Field(default=None, max_length=1000)


class BuyerOwnReviewOut(BaseModel):
    """Свой отзыв позиции — для предзаполнения формы правки в «Моих покупках»."""

    rating: int
    body: str | None


class OrderItemOut(BaseModel):
    product_id: int
    title: str
    qty: int
    price: Decimal
    # оценён ли товар покупателем (для кнопки «Оценить покупки»)
    reviewed: bool = False
    # сам отзыв, если он есть — форма правки открывается уже заполненной
    my_review: BuyerOwnReviewOut | None = None


class OrderOut(BaseModel):
    id: int
    status: str
    total: Decimal
    currency: str
    items: list[OrderItemOut]
    payment_url: str | None = None  # ссылка на оплату в @CryptoBot


@router.get("", response_model=ShopOut)
async def get_shop(ctx: BuyerContext = Depends(get_buyer)) -> ShopOut:
    avatar = (
        await ctx.session.execute(
            select(BotAvatar.token).where(BotAvatar.bot_id == ctx.bot.id)
        )
    ).scalar_one_or_none()
    if avatar is None:
        # магазину, подключённому до появления аватаров, докачиваем фото лениво;
        # неудача (нет фото, Telegram недоступен) витрину не ломает
        try:
            await refresh_bot_avatar(ctx.session, ctx.bot)
            await ctx.session.commit()
        except IntegrityError:
            # bot_id уникален: два покупателя открыли витрину одновременно и
            # оба скачали аватар. Проигравший просто перечитает чужую строку —
            # 500 на витрине из-за украшения недопустим
            await ctx.session.rollback()
        avatar = (
            await ctx.session.execute(
                select(BotAvatar.token).where(BotAvatar.bot_id == ctx.bot.id)
            )
        ).scalar_one_or_none()

    result = await ctx.session.execute(
        select(Product)
        .where(Product.bot_id == ctx.bot.id, Product.is_active.is_(True))
        .order_by(Product.id)
    )
    products = result.scalars().all()

    # средний рейтинг одним агрегатом на все товары магазина
    ratings: dict[int, tuple[float, int]] = {}
    if products:
        rows = await ctx.session.execute(
            select(
                ProductReview.product_id,
                func.avg(ProductReview.rating),
                func.count(),
            )
            .where(
                ProductReview.bot_id == ctx.bot.id,
                ProductReview.product_id.in_([p.id for p in products]),
            )
            .group_by(ProductReview.product_id)
        )
        ratings = {pid: (float(avg), cnt) for pid, avg, cnt in rows.all()}

    out = []
    for p in products:
        product_out = ProductOut.model_validate(p)
        product_out.avg_rating, product_out.reviews_count = ratings.get(p.id, (None, 0))
        out.append(product_out)
    return ShopOut(
        shop_name=f"@{ctx.bot.bot_username}",
        shop_avatar_url=f"/api/bot-avatars/{avatar}" if avatar else None,
        products=out,
    )


class EventIn(BaseModel):
    type: str  # shop_open | product_view | checkout_start
    product_id: int | None = None


EVENT_TYPES = {"shop_open", "product_view", "checkout_start"}


@router.post("/events")
async def track_event(payload: EventIn, ctx: BuyerContext = Depends(get_buyer)) -> dict:
    """Событие витрины для статистики продавца. Незнакомый тип молча
    игнорируется, чтобы старые клиенты не получали ошибок после обновлений."""
    if payload.type not in EVENT_TYPES:
        return {"status": "ignored"}
    ctx.session.add(
        ShopEvent(
            bot_id=ctx.bot.id,
            customer_id=ctx.customer.id,
            product_id=payload.product_id,
            type=payload.type,
        )
    )
    await ctx.session.commit()
    return {"status": "ok"}


@router.post("/orders", response_model=OrderOut)
async def create_order(payload: OrderIn, ctx: BuyerContext = Depends(get_buyer)) -> OrderOut:
    product_ids = [i.product_id for i in payload.items]
    result = await ctx.session.execute(
        select(Product).where(
            Product.id.in_(product_ids),
            Product.bot_id == ctx.bot.id,  # товары чужого магазина в заказ не попадут
            Product.is_active.is_(True),
        )
    )
    products = {p.id: p for p in result.scalars().all()}
    missing = set(product_ids) - set(products)
    if missing:
        raise HTTPException(status_code=400, detail=f"products not available: {sorted(missing)}")

    # Сток проверяем по суммарному qty (товар может прийти двумя строками).
    # Финальная проверка — в вебхуке оплаты; здесь отсекаем очевидный оверселл
    qty_by_product: dict[int, int] = {}
    for item in payload.items:
        qty_by_product[item.product_id] = qty_by_product.get(item.product_id, 0) + item.qty
    for product_id, qty in qty_by_product.items():
        stock = products[product_id].stock
        if stock is not None and qty > stock:
            raise HTTPException(
                status_code=400,
                detail=f"insufficient stock for «{products[product_id].title}»: {stock} left",
            )

    # Сумма считается только на сервере, по текущим ценам из БД
    total = sum(products[i.product_id].price * i.qty for i in payload.items)

    order = Order(
        seller_id=ctx.bot.seller_id,
        bot_id=ctx.bot.id,
        customer_id=ctx.customer.id,
        total=total,
        currency="USDT",
        comment=payload.comment,
    )
    ctx.session.add(order)
    await ctx.session.flush()
    for item in payload.items:
        ctx.session.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                qty=item.qty,
                price=products[item.product_id].price,
            )
        )
    await ctx.session.commit()

    from app.payments.service import create_invoice_for_order

    try:
        payment_url = await create_invoice_for_order(order.id, Decimal(total))
    except Exception:
        # Заказ уже создан, оплату можно повторить — checkout не роняем,
        # но причину пишем в лог: иначе «кнопка не работает» не диагностируется
        logger.exception("Не удалось создать инвойс для заказа %s", order.id)
        payment_url = None

    return OrderOut(
        id=order.id,
        status=order.status,
        total=Decimal(total),
        currency=order.currency,
        payment_url=payment_url,
        items=[
            OrderItemOut(
                product_id=i.product_id,
                title=products[i.product_id].title,
                qty=i.qty,
                price=products[i.product_id].price,
            )
            for i in payload.items
        ],
    )


@router.get("/orders/my", response_model=list[OrderOut])
async def my_orders(ctx: BuyerContext = Depends(get_buyer)) -> list[OrderOut]:
    result = await ctx.session.execute(
        select(Order)
        .where(Order.customer_id == ctx.customer.id)
        .order_by(Order.id.desc())
        .limit(50)
    )
    orders = result.scalars().all()

    # свои отзывы по всем заказам страницы — одним запросом; из них и флаг
    # reviewed, и данные для предзаполнения формы правки
    my_reviews: dict[tuple[int, int], ProductReview] = {}
    if orders:
        rows = await ctx.session.execute(
            select(ProductReview).where(
                ProductReview.customer_id == ctx.customer.id,
                ProductReview.order_id.in_([o.id for o in orders]),
            )
        )
        my_reviews = {(r.order_id, r.product_id): r for r in rows.scalars().all()}

    # состав всех заказов одним запросом: экран «Мои покупки» обновляется сам
    # раз в 10 секунд, и запрос на каждый заказ множился бы на этот опрос
    items_by_order: dict[int, list[tuple[OrderItem, str]]] = {}
    if orders:
        items_result = await ctx.session.execute(
            select(OrderItem, Product.title)
            .join(Product, Product.id == OrderItem.product_id)
            .where(OrderItem.order_id.in_([o.id for o in orders]))
        )
        for item, title in items_result.all():
            items_by_order.setdefault(item.order_id, []).append((item, title))

    out: list[OrderOut] = []
    for order in orders:
        out.append(
            OrderOut(
                id=order.id,
                status=order.status,
                total=order.total,
                currency=order.currency,
                items=[
                    OrderItemOut(
                        product_id=i.product_id,
                        title=title,
                        qty=i.qty,
                        price=i.price,
                        reviewed=(order.id, i.product_id) in my_reviews,
                        my_review=(
                            BuyerOwnReviewOut(
                                rating=review.rating, body=review.body
                            )
                            if (review := my_reviews.get((order.id, i.product_id)))
                            is not None
                            else None
                        ),
                    )
                    for i, title in items_by_order.get(order.id, [])
                ],
            )
        )
    return out


# --------------------------------------------------------------------------
# Чат заказа: покупатель отвечает в диалоге с ботом магазина, история видна
# и ему (эти эндпоинты), и продавцу в кабинете. Личность не раскрывается.
# --------------------------------------------------------------------------


class BuyerChatMessageOut(BaseModel):
    id: int
    sender: str  # seller | customer
    body: str
    image_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BuyerOrderChatOut(BaseModel):
    status: str  # active | locked_by_timeout | archived
    can_send: bool
    closes_at: datetime | None
    messages: list[BuyerChatMessageOut]


class BuyerChatMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


async def _own_order_with_chat(ctx: BuyerContext, order_id: int) -> tuple[Order, OrderChat]:
    """Заказ и его чат, принадлежащие именно этому покупателю. Чужой заказ —
    403: подменённый order_id не должен выдавать даже факт существования чата."""
    from app.services.chat import get_or_create_chat

    order = await ctx.session.get(Order, order_id)
    if order is None or order.bot_id != ctx.bot.id or order.customer_id != ctx.customer.id:
        raise HTTPException(status_code=403, detail="foreign order")
    chat = await get_or_create_chat(ctx.session, order)
    if chat is None:
        raise HTTPException(status_code=403, detail="chat_not_available")
    return order, chat


@router.get("/orders/{order_id}/chat", response_model=BuyerOrderChatOut)
async def get_order_chat(order_id: int, ctx: BuyerContext = Depends(get_buyer)) -> BuyerOrderChatOut:
    from app.services.chat import chat_is_open, closes_at, read_history

    order, chat = await _own_order_with_chat(ctx, order_id)
    messages = await read_history(ctx.session, chat.id)
    await ctx.session.commit()  # чат мог создаться этим вызовом
    return BuyerOrderChatOut(
        status=chat.status,
        can_send=chat_is_open(order),
        closes_at=closes_at(order),
        messages=[BuyerChatMessageOut.model_validate(m) for m in messages],
    )


@router.post("/orders/{order_id}/chat/messages", response_model=BuyerChatMessageOut)
async def send_order_chat_message(
    order_id: int, payload: BuyerChatMessageIn, ctx: BuyerContext = Depends(get_buyer)
) -> BuyerChatMessageOut:
    """Сообщение покупателя. Пишется в историю сразу; продавцу уходит пуш в
    hub-бот без деталей личности, сам текст он увидит в кабинете."""
    from app.services.chat import (
        ChatLockedError,
        RateLimitedError,
        notify_seller,
        send_message,
    )

    order, chat = await _own_order_with_chat(ctx, order_id)
    try:
        message = await send_message(ctx.session, chat, order, "customer", payload.body)
    except ChatLockedError:
        raise HTTPException(status_code=403, detail="chat_locked")
    except RateLimitedError:
        raise HTTPException(status_code=429, detail="too_many_messages")

    out = BuyerChatMessageOut.model_validate(message)
    seller_tg = (await ctx.session.get(Seller, order.seller_id)).telegram_id
    await ctx.session.commit()

    await notify_seller(seller_tg, order.id)
    return out


# --------------------------------------------------------------------------
# Отзывы: оценка товара доступна только покупателю его доставленного заказа.
# Наружу идут оценка, текст, случайный псевдоним автора и ответ продавца —
# но никакие реальные данные о покупателе.
# --------------------------------------------------------------------------


class PublicReviewOut(BaseModel):
    rating: int
    body: str | None
    # случайный псевдоним («Анна К.»), к личности не привязан
    author_name: str | None
    reply_body: str | None
    reply_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewItemIn(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    body: str | None = Field(default=None, max_length=1000)


class ReviewsIn(BaseModel):
    items: list[ReviewItemIn] = Field(min_length=1, max_length=20)


class BuyerReviewOut(BaseModel):
    id: int
    product_id: int
    rating: int
    body: str | None
    author_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


async def _own_delivered_order(ctx: BuyerContext, order_id: int) -> Order:
    """Заказ этого покупателя в статусе delivered; иначе 403/400 без деталей."""
    order = await ctx.session.get(Order, order_id)
    if order is None or order.bot_id != ctx.bot.id or order.customer_id != ctx.customer.id:
        raise HTTPException(status_code=403, detail="foreign order")
    if order.status != "delivered":
        raise HTTPException(status_code=400, detail=f"order is {order.status}, not delivered")
    return order


@router.get("/products/{product_id}/reviews", response_model=list[PublicReviewOut])
async def product_reviews(
    product_id: int, ctx: BuyerContext = Depends(get_buyer)
) -> list[PublicReviewOut]:
    product = await ctx.session.get(Product, product_id)
    if product is None or product.bot_id != ctx.bot.id or not product.is_active:
        raise HTTPException(status_code=404, detail="product not found")
    result = await ctx.session.execute(
        select(ProductReview)
        .where(ProductReview.product_id == product_id)
        .order_by(ProductReview.id.desc())
        .limit(50)
    )
    return [PublicReviewOut.model_validate(r) for r in result.scalars().all()]


@router.post("/orders/{order_id}/reviews", response_model=list[BuyerReviewOut])
async def leave_review(
    order_id: int, payload: ReviewsIn, ctx: BuyerContext = Depends(get_buyer)
) -> list[BuyerReviewOut]:
    """Оценки позиций своего доставленного заказа. Повторная отправка по той же
    паре (заказ, товар) правит оценку — передумать можно. Пуш продавцу уходит
    только на новые отзывы, правки не спамят."""
    order = await _own_delivered_order(ctx, order_id)

    items_result = await ctx.session.execute(
        select(OrderItem, Product.title)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order.id)
    )
    titles: dict[int, str] = {}
    for i, title in items_result.all():
        titles[i.product_id] = title
    foreign = [i.product_id for i in payload.items if i.product_id not in titles]
    if foreign:
        raise HTTPException(status_code=400, detail=f"products not in this order: {foreign}")

    # существующие отзывы заказа — их обновляем, остальные создаём
    existing_rows = await ctx.session.execute(
        select(ProductReview).where(ProductReview.order_id == order.id)
    )
    by_product = {r.product_id: r for r in existing_rows.scalars().all()}

    out: list[BuyerReviewOut] = []
    created: list[tuple[str, int, str | None]] = []
    for item in payload.items:
        review = by_product.get(item.product_id)
        if review is None:
            # автор — Telegram-имя покупателя (не юзернейм); без имени в профиле
            # остаётся случайный псевдоним
            display_name = (ctx.customer.first_name or "").strip()[:64]
            review = ProductReview(
                bot_id=ctx.bot.id,
                product_id=item.product_id,
                order_id=order.id,
                customer_id=ctx.customer.id,
                rating=item.rating,
                body=item.body,
                author_name=display_name or random_author_name(),
            )
            ctx.session.add(review)
            await ctx.session.flush()
            created.append((titles[item.product_id], item.rating, item.body))
        else:
            review.rating = item.rating
            review.body = item.body
        out.append(BuyerReviewOut.model_validate(review))
    await ctx.session.commit()

    seller_tg = (await ctx.session.get(Seller, order.seller_id)).telegram_id
    for title, rating, body in created:
        await notify_new_review(seller_tg, title, rating, body)
    return out


@router.delete("/orders/{order_id}/reviews/{product_id}")
async def delete_review(
    order_id: int, product_id: int, ctx: BuyerContext = Depends(get_buyer)
) -> dict:
    """Покупатель передумал: свой отзыв на позицию доставленного заказа можно
    снять целиком. Средний рейтинг пересчитается при следующей выдаче витрины."""
    order = await _own_delivered_order(ctx, order_id)
    result = await ctx.session.execute(
        select(ProductReview).where(
            ProductReview.order_id == order.id,
            ProductReview.product_id == product_id,
            ProductReview.customer_id == ctx.customer.id,
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="review not found")
    await ctx.session.delete(review)
    await ctx.session.commit()
    return {"status": "deleted"}
