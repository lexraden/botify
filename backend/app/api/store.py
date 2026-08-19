"""API витрины: покупатель внутри seller-бота. Всё отфильтровано по продавцу бота."""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import BuyerContext, get_buyer
from app.models import Order, OrderItem, Product, ShopEvent

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
