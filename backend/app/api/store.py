"""API витрины: покупатель внутри seller-бота. Всё отфильтровано по продавцу бота."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import BuyerContext, get_buyer, get_buyer_any_shop
from app.config import get_settings
from app.models import (
    Customer,
    Order,
    OrderChat,
    OrderItem,
    Product,
    ProductReview,
    Seller,
    ShopEvent,
    ShopLogo,
)
from app.models.orders import PAID_STATUSES
from app.services import seller_texts
from app.services.reviews import notify_new_review, random_author_name
from app.services.variants import variant_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/store/{bot_id}")


class VariantOut(BaseModel):
    """Вариация на витрине. Цена, остаток и фото у каждой свои."""

    id: int
    sku: str | None
    attributes: dict | None
    # None — у вариации своего названия/описания нет, показываем товарное
    title: str | None = None
    description: str | None = None
    price: Decimal
    compare_at_price: Decimal | None
    stock: int | None
    images: list | None

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: int
    type: str
    title: str
    description: str | None
    image_url: str | None
    price: Decimal
    # зачёркнутая «старая» цена; None — скидки нет. У товара с вариациями
    # всегда None: там скидка своя у каждой вариации
    compare_at_price: Decimal | None = None
    currency: str
    # остаток; None — не ограничен, 0 — «нет в наличии»
    stock: int | None
    # рейтинг: среднее по отзывам покупателей; нет отзывов — None и ноль
    avg_rating: float | None = None
    reviews_count: int = 0
    # Пусто — у товара нет вариаций, покупается он сам. Иначе покупатель
    # обязан выбрать вариацию: цена и остаток товара тут лишь витринные
    # («от 500», сумма остатков), а платят за конкретную
    variants: list[VariantOut] = []

    model_config = {"from_attributes": True}


class ShopOut(BaseModel):
    shop_name: str
    products: list[ProductOut]
    # Куда писать, если проблема с заказом. Пусто — в профиле нет кнопки:
    # лучше её отсутствие, чем ссылка не туда.
    support_url: str | None = None
    # логотип из кабинета; None — в шапке первая буква имени вместо кружка
    logo_url: str | None = None
    # средний рейтинг по всем отзывам магазина; нет отзывов — None
    rating: float | None = None
    # состоявшиеся продажи — оплаченные заказы (PAID_STATUSES)
    sales_count: int = 0


class CartItemIn(BaseModel):
    product_id: int
    # None — товар без вариаций. У товара с вариациями обязателен: без него
    # непонятно, за какой размер человек заплатил
    variant_id: int | None = None
    qty: int = Field(ge=1, le=99)


class DeliveryIn(BaseModel):
    """Куда везти. Обязательна, если в заказе есть физический товар: без неё
    продавец не может отправить посылку и идёт выяснять адрес в чат.
    Имя/телефон больше не собираем (лишний ввод стоял конверсии чекаута),
    но поле осталось — у старых заказов и старых клиентов оно приходит."""

    name: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    address: str = Field(min_length=1, max_length=512)


class OrderIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    comment: str | None = Field(default=None, max_length=1000)
    delivery: DeliveryIn | None = None


class BuyerOwnReviewOut(BaseModel):
    """Свой отзыв позиции — для предзаполнения формы правки в «Моих покупках».
    Статус нужен, чтобы показать «на проверке», пока продавец не одобрил."""

    rating: int
    body: str | None
    status: str


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
    # когда заказ перестанет ждать оплату; None — не истекает (оплачен/старый)
    expires_at: datetime | None = None


@router.get("", response_model=ShopOut)
async def get_shop(ctx: BuyerContext = Depends(get_buyer)) -> ShopOut:
    result = await ctx.session.execute(
        select(Product)
        # без selectinload вариации подгружались бы лениво уже вне сессии
        .options(selectinload(Product.variants))
        .where(Product.bot_id == ctx.bot.id, Product.is_active.is_(True))
        .order_by(Product.id)
    )
    products = result.scalars().all()

    # средний рейтинг одним агрегатом на все товары магазина; в рейтинг
    # попадают только опубликованные отзывы — ожидающие модерации не видны
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
                ProductReview.status == "published",
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

    # идентичность и trust-сигналы шапки: лого, рейтинг магазина по всем
    # его отзывам одним агрегатом, число состоявшихся продаж
    logo = (
        await ctx.session.execute(select(ShopLogo).where(ShopLogo.bot_id == ctx.bot.id))
    ).scalar_one_or_none()
    avg_rating, total_reviews = (
        await ctx.session.execute(
            select(func.avg(ProductReview.rating), func.count()).where(
                ProductReview.bot_id == ctx.bot.id,
                ProductReview.status == "published",
            )
        )
    ).one()
    sales_count = (
        await ctx.session.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.bot_id == ctx.bot.id, Order.status.in_(PAID_STATUSES))
        )
    ).scalar_one()

    return ShopOut(
        shop_name=ctx.bot.shop_name or f"@{ctx.bot.bot_username}",
        products=out,
        support_url=get_settings().support_url or None,
        logo_url=f"/api/shop-logos/{logo.token}" if logo else None,
        rating=float(avg_rating) if total_reviews else None,
        sales_count=sales_count,
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
    product_id = payload.product_id
    if product_id is not None:
        # чужой/удалённый товар в статистику не попадает: событие остаётся,
        # но без привязки к товару — витрина не должна уметь 500-ить на id
        product = await ctx.session.get(Product, product_id)
        if product is None or product.bot_id != ctx.bot.id:
            product_id = None
    ctx.session.add(
        ShopEvent(
            bot_id=ctx.bot.id,
            customer_id=ctx.customer.id,
            product_id=product_id,
            type=payload.type,
        )
    )
    await ctx.session.commit()
    return {"status": "ok"}


@router.post("/orders", response_model=OrderOut)
async def create_order(payload: OrderIn, ctx: BuyerContext = Depends(get_buyer)) -> OrderOut:
    product_ids = [i.product_id for i in payload.items]
    result = await ctx.session.execute(
        select(Product)
        .options(selectinload(Product.variants))
        .where(
            Product.id.in_(product_ids),
            Product.bot_id == ctx.bot.id,  # товары чужого магазина в заказ не попадут
            Product.is_active.is_(True),
        )
    )
    products = {p.id: p for p in result.scalars().all()}
    missing = set(product_ids) - set(products)
    if missing:
        raise HTTPException(status_code=400, detail=f"products not available: {sorted(missing)}")

    # Вариацию сверяем с товаром, а не берём на слово: иначе покупатель мог бы
    # прислать id дешёвой вариации к дорогому товару и заплатить не за то.
    chosen: dict[int, object] = {}
    for item in payload.items:
        product = products[item.product_id]
        active = [v for v in product.variants if v.is_active]
        if not active:
            if item.variant_id is not None:
                raise HTTPException(
                    status_code=400, detail=f"product {item.product_id} has no variants"
                )
            continue
        if item.variant_id is None:
            raise HTTPException(
                status_code=400, detail=f"variant_required for product {item.product_id}"
            )
        variant = next((v for v in active if v.id == item.variant_id), None)
        if variant is None:
            raise HTTPException(
                status_code=400, detail=f"variant not available: {item.variant_id}"
            )
        chosen[item.variant_id] = variant

    # Физический товар без адреса отправить некуда — это единственные данные
    # покупателя, которые видит продавец. У цифровых заказов адрес не спрашиваем.
    needs_delivery = any(products[i.product_id].type == "physical" for i in payload.items)
    if needs_delivery and payload.delivery is None:
        raise HTTPException(status_code=400, detail="delivery_required")

    # Сток проверяем по суммарному qty (товар может прийти двумя строками).
    # Финальная проверка — в вебхуке оплаты; здесь отсекаем очевидный оверселл
    # Ключ — (товар, вариация): одна и та же футболка в двух размерах имеет
    # два независимых остатка, и складывать их в одну проверку нельзя
    qty_by_key: dict[tuple[int, int | None], int] = {}
    for item in payload.items:
        key = (item.product_id, item.variant_id)
        qty_by_key[key] = qty_by_key.get(key, 0) + item.qty
    for (product_id, variant_id), qty in qty_by_key.items():
        source = chosen[variant_id] if variant_id is not None else products[product_id]
        stock = source.stock
        if stock is not None and qty > stock:
            raise HTTPException(
                status_code=400,
                detail=f"insufficient stock for «{products[product_id].title}»: {stock} left",
            )

    # Сумма считается только на сервере, по текущим ценам из БД: у товара с
    # вариациями платят за вариацию, у остальных — за сам товар
    total = sum(
        (chosen[i.variant_id].price if i.variant_id is not None else products[i.product_id].price)
        * i.qty
        for i in payload.items
    )

    # Жизнь заказа = жизнь счёта в Crypto Pay: неоплаченная корзина не должна
    # висеть в «Моих покупках» вечно. По кнопке «Оплатить» счётчик пойдёт заново.
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=get_settings().unpaid_order_ttl_minutes
    )

    order = Order(
        seller_id=ctx.bot.seller_id,
        bot_id=ctx.bot.id,
        customer_id=ctx.customer.id,
        total=total,
        currency="USDT",
        comment=payload.comment,
        expires_at=expires_at,
        delivery=(
            payload.delivery.model_dump(exclude_none=True)
            if needs_delivery and payload.delivery
            else None
        ),
    )
    ctx.session.add(order)
    await ctx.session.flush()
    for item in payload.items:
        variant = chosen.get(item.variant_id) if item.variant_id is not None else None
        ctx.session.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                # снимок свойств рядом со снимком цены: продавец переименует
                # размеры, а в старом заказе должно остаться купленное
                variant_label=variant_label(variant.attributes) if variant else None,
                qty=item.qty,
                price=variant.price if variant else products[item.product_id].price,
            )
        )
    await ctx.session.commit()

    from app.payments.service import create_invoice_for_order

    try:
        payment_url = await create_invoice_for_order(order.id, Decimal(total), ctx.bot)
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
        expires_at=order.expires_at,
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


class PayOut(BaseModel):
    payment_url: str | None = None


async def _own_order(ctx: BuyerContext, order_id: int) -> Order:
    order = await ctx.session.get(Order, order_id)
    if order is None or order.bot_id != ctx.bot.id or order.customer_id != ctx.customer.id:
        raise HTTPException(status_code=403, detail="foreign order")
    return order


@router.post("/orders/{order_id}/pay")
async def pay_order(order_id: int, ctx: BuyerContext = Depends(get_buyer)) -> PayOut:
    """Свежая ссылка на оплату своего неоплаченного заказа. Инвойс создаётся
    новый: у ссылки из чекаута час жизни, к моменту «Оплатить» она уже может
    быть мертва.

    Предыдущий счёт снимается, а не оставляется дотлевать: иначе у заказа
    оказывается несколько живых ссылок, и оплата второй из них проходит мимо
    заказа — деньги приняты, не сделано ничего.
    """
    from app.payments.service import create_invoice_for_order, discard_invoice

    order = await _own_order(ctx, order_id)
    if order.status != "pending_payment":
        raise HTTPException(
            status_code=409, detail=f"order is {order.status}, not awaiting payment"
        )
    await discard_invoice(order.invoice_id)
    try:
        payment_url = await create_invoice_for_order(order.id, Decimal(order.total), ctx.bot)
    except Exception:
        logger.exception("Повторный инвойс для заказа %s создать не удалось", order.id)
        raise HTTPException(status_code=502, detail="invoice_failed") from None
    # Выписали новый часовой счёт — дали заказу столько же. Иначе покупатель,
    # нажавший «Оплатить» на 59-й минуте, получил бы счёт на минуту.
    order.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=get_settings().unpaid_order_ttl_minutes
    )
    await ctx.session.commit()
    return PayOut(payment_url=payment_url)


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, ctx: BuyerContext = Depends(get_buyer_any_shop)) -> dict:
    """Покупатель передумал: свой неоплаченный заказ отменяется им сам.

    Статус проверяется под блокировкой строки — заказ, который вебхук успел
    оплатить между нажатиями «Оплатить» и «Отменить», не отменится. Счёт
    снимается в Crypto Pay, иначе по оставшейся в переписке ссылке можно
    заплатить за отменённый заказ, и деньги уйдут в никуда.
    """
    from app.payments.service import discard_invoice

    result = await ctx.session.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None or order.bot_id != ctx.bot.id or order.customer_id != ctx.customer.id:
        raise HTTPException(status_code=403, detail="foreign order")
    if order.status != "pending_payment":
        raise HTTPException(status_code=409, detail=f"order is {order.status}")
    order.status = "cancelled"
    invoice_id = order.invoice_id
    await ctx.session.commit()

    # после коммита: снятие счёта — сетевой вызов, и его неудача не должна
    # откатывать уже принятую отмену
    await discard_invoice(invoice_id)
    return {"status": "cancelled"}


@router.post("/orders/{order_id}/received")
async def confirm_received(
    order_id: int, ctx: BuyerContext = Depends(get_buyer_any_shop)
) -> dict:
    """Покупатель получил заказ.

    Отметку ставит он, а не продавец: «Отправлен» и «Доставлен» — разные
    события, между ними дни пути. От `delivered_at` считается окно чата, и
    начинать его в момент отправки значит закрывать связь с продавцом ровно
    тогда, когда посылка может потеряться. Оценить покупку тоже можно только
    после получения — раньше и оценивать нечего.
    """
    order = await _own_order(ctx, order_id)
    if order.status != "fulfilled":
        raise HTTPException(status_code=409, detail=f"order is {order.status}")
    order.status = "delivered"
    order.delivered_at = func.now()
    await ctx.session.commit()
    return {"status": "delivered"}


@router.get("/orders/my", response_model=list[OrderOut])
async def my_orders(ctx: BuyerContext = Depends(get_buyer_any_shop)) -> list[OrderOut]:
    """Свои заказы. Отменённые не показываются: список — это то, что покупатель
    ждёт оплаты или получения. Строки в базе остаются — сверка платежей
    (app/payments/reconcile.py) и статистика продолжают их видеть."""
    result = await ctx.session.execute(
        select(Order)
        .where(Order.customer_id == ctx.customer.id, Order.status != "cancelled")
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
                expires_at=order.expires_at,
                items=[
                    OrderItemOut(
                        product_id=i.product_id,
                        title=title,
                        qty=i.qty,
                        price=i.price,
                        reviewed=(order.id, i.product_id) in my_reviews,
                        my_review=(
                            BuyerOwnReviewOut(
                                rating=review.rating,
                                body=review.body,
                                status=review.status,
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
async def get_order_chat(order_id: int, ctx: BuyerContext = Depends(get_buyer_any_shop)) -> BuyerOrderChatOut:
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
    order_id: int, payload: BuyerChatMessageIn, ctx: BuyerContext = Depends(get_buyer_any_shop)
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
    seller = await ctx.session.get(Seller, order.seller_id)
    seller_tg = seller.telegram_id
    await ctx.session.commit()

    await notify_seller(seller_tg, order.id, locale=seller_texts.seller_locale(seller))
    return out


# --------------------------------------------------------------------------
# Отзывы: оценка товара доступна только покупателю его доставленного заказа.
# Наружу идут оценка, текст, имя автора и ответ продавца. Имя — настоящее,
# из профиля Telegram (без юзернейма): живые подписи вызывают больше доверия
# к отзывам. Покупателя об этом предупреждают в форме оценки.
# --------------------------------------------------------------------------


class PublicReviewOut(BaseModel):
    rating: int
    body: str | None
    # имя автора: first_name из Telegram, у безымянных — псевдоним «Анна К.»
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
    status: str
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
        .where(ProductReview.product_id == product_id, ProductReview.status == "published")
        .order_by(ProductReview.id.desc())
        .limit(50)
    )
    return [PublicReviewOut.model_validate(r) for r in result.scalars().all()]


@router.post("/orders/{order_id}/reviews", response_model=list[BuyerReviewOut])
async def leave_review(
    order_id: int, payload: ReviewsIn, ctx: BuyerContext = Depends(get_buyer_any_shop)
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

    # Порог модерации: высокая оценка публикуется сразу, низкая ждёт продавца.
    # Правка пересчитывает статус по тому же порогу (5→2 уходит на проверку,
    # 2→5 публикуется), правка отклонённого возвращает его в ожидание.
    auto_publish_min = get_settings().review_auto_publish_min
    # время в Python, не func.now(): модель валидируется сразу после flush,
    # а SQL-выражение в атрибуте async-сессия без refresh не отдаст
    now = datetime.now(timezone.utc)

    def status_for(rating: int, previous: str | None = None) -> str:
        if previous == "rejected":
            return "pending"
        return "published" if rating >= auto_publish_min else "pending"

    out: list[BuyerReviewOut] = []
    created: list[tuple[str, int, str | None]] = []
    for item in payload.items:
        review = by_product.get(item.product_id)
        if review is None:
            # автор — Telegram-имя покупателя (не юзернейм); у тех, у кого имени
            # в профиле нет, подпись остаётся псевдонимом
            display_name = (ctx.customer.first_name or "").strip()[:64]
            review = ProductReview(
                bot_id=ctx.bot.id,
                product_id=item.product_id,
                order_id=order.id,
                customer_id=ctx.customer.id,
                rating=item.rating,
                body=item.body,
                author_name=display_name or random_author_name(),
                status=status_for(item.rating),
                moderated_at=now if item.rating >= auto_publish_min else None,
            )
            ctx.session.add(review)
            await ctx.session.flush()
            created.append((titles[item.product_id], item.rating, item.body))
        else:
            review.rating = item.rating
            review.body = item.body
            new_status = status_for(item.rating, review.status)
            if new_status != review.status:
                review.status = new_status
                review.moderated_at = now if new_status == "published" else None
        out.append(BuyerReviewOut.model_validate(review))
    await ctx.session.commit()

    seller = await ctx.session.get(Seller, order.seller_id)
    seller_tg = seller.telegram_id
    for title, rating, body in created:
        await notify_new_review(
            seller_tg, title, rating, body, locale=seller_texts.seller_locale(seller)
        )
    return out


@router.delete("/orders/{order_id}/reviews/{product_id}")
async def delete_review(
    order_id: int, product_id: int, ctx: BuyerContext = Depends(get_buyer_any_shop)
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
