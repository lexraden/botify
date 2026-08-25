"""API витрины: покупатель внутри seller-бота. Всё отфильтровано по продавцу бота."""

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BuyerContext, get_buyer
from app.models import Customer, Order, OrderChat, OrderItem, Product, Seller, ShopEvent

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

    model_config = {"from_attributes": True}


class ShopOut(BaseModel):
    shop_name: str
    products: list[ProductOut]


class CartItemIn(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=99)


class OrderIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    comment: str | None = Field(default=None, max_length=1000)


class OrderItemOut(BaseModel):
    product_id: int
    title: str
    qty: int
    price: Decimal


class OrderOut(BaseModel):
    id: int
    status: str
    total: Decimal
    currency: str
    items: list[OrderItemOut]
    payment_url: str | None = None  # ссылка на оплату в @CryptoBot


@router.get("", response_model=ShopOut)
async def get_shop(ctx: BuyerContext = Depends(get_buyer)) -> ShopOut:
    result = await ctx.session.execute(
        select(Product)
        .where(Product.bot_id == ctx.bot.id, Product.is_active.is_(True))
        .order_by(Product.id)
    )
    products = result.scalars().all()
    return ShopOut(
        shop_name=f"@{ctx.bot.bot_username}",
        products=[ProductOut.model_validate(p) for p in products],
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
    out: list[OrderOut] = []
    for order in orders:
        items_result = await ctx.session.execute(
            select(OrderItem, Product.title)
            .join(Product, Product.id == OrderItem.product_id)
            .where(OrderItem.order_id == order.id)
        )
        out.append(
            OrderOut(
                id=order.id,
                status=order.status,
                total=order.total,
                currency=order.currency,
                items=[
                    OrderItemOut(product_id=i.product_id, title=title, qty=i.qty, price=i.price)
                    for i, title in items_result.all()
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
