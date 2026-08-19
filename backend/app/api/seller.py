"""API кабинета продавца (Mini App открыт из hub-бота)."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_seller
from app.db import get_api_session
from app.models import Customer, Mailing, Order, OrderItem, Payout, Product, Seller, SellerBot

router = APIRouter(prefix="/seller")

PRODUCT_TYPES = {"physical", "digital", "service"}


class BotOut(BaseModel):
    id: int
    bot_username: str
    webhook_status: str

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    onboarding_step: str
    cryptobot_connected: bool
    commission_pct: Decimal
    plan: str
    bots: list[BotOut]
    customers_count: int
    orders_count: int


class ProductIn(BaseModel):
    type: str
    title: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, max_length=512)
    price: Decimal = Field(gt=0)
    digital_content: dict | None = None
    is_active: bool = True


class ProductOut(ProductIn):
    id: int
    currency: str

    model_config = {"from_attributes": True}


class SellerOrderOut(BaseModel):
    id: int
    status: str
    total: Decimal
    currency: str
    comment: str | None
    customer_username: str | None
    customer_first_name: str | None


@router.get("/me", response_model=MeOut)
async def me(
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> MeOut:
    bots = (
        (await session.execute(select(SellerBot).where(SellerBot.seller_id == seller.id)))
        .scalars()
        .all()
    )
    customers_count = (
        await session.execute(
            select(func.count()).select_from(Customer).where(Customer.seller_id == seller.id)
        )
    ).scalar_one()
    orders_count = (
        await session.execute(
            select(func.count()).select_from(Order).where(Order.seller_id == seller.id)
        )
    ).scalar_one()
    return MeOut(
        onboarding_step=seller.onboarding_step,
        cryptobot_connected=seller.cryptobot_connected,
        commission_pct=seller.commission_pct,
        plan=seller.plan,
        bots=[BotOut.model_validate(b) for b in bots],
        customers_count=customers_count,
        orders_count=orders_count,
    )


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> list[ProductOut]:
    result = await session.execute(
        select(Product).where(Product.seller_id == seller.id).order_by(Product.id.desc())
    )
    return [ProductOut.model_validate(p) for p in result.scalars().all()]


@router.post("/products", response_model=ProductOut)
async def create_product(
    payload: ProductIn,
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> ProductOut:
    if payload.type not in PRODUCT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(PRODUCT_TYPES)}")
    product = Product(seller_id=seller.id, **payload.model_dump())
    session.add(product)
    await session.commit()
    return ProductOut.model_validate(product)


async def _own_product(session: AsyncSession, seller: Seller, product_id: int) -> Product:
    product = await session.get(Product, product_id)
    if product is None or product.seller_id != seller.id:
        raise HTTPException(status_code=404, detail="product not found")
    return product


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductIn,
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> ProductOut:
    if payload.type not in PRODUCT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(PRODUCT_TYPES)}")
    product = await _own_product(session, seller, product_id)
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    await session.commit()
    return ProductOut.model_validate(product)


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    product = await _own_product(session, seller, product_id)
    # Товар мог участвовать в заказах (FK RESTRICT) — деактивируем, а не удаляем
    used = (
        await session.execute(
            select(func.count()).select_from(OrderItem).where(OrderItem.product_id == product.id)
        )
    ).scalar_one()
    if used:
        product.is_active = False
        await session.commit()
        return {"status": "deactivated"}
    await session.delete(product)
    await session.commit()
    return {"status": "deleted"}


class FulfillIn(BaseModel):
    tracking: str | None = Field(default=None, max_length=256)  # трек-номер
    url: str | None = Field(default=None, max_length=512)       # ссылка (файл/инвайт)
    note: str | None = Field(default=None, max_length=1000)     # координаты/примечание


@router.post("/orders/{order_id}/fulfill")
async def fulfill_order(
    order_id: int,
    payload: FulfillIn,
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Продавец прикрепляет трек/ссылку/примечание -> бот пересылает покупателю,
    затем платформа отправляет продавцу его долю (Crypto Pay transfer)."""
    if not (payload.tracking or payload.url or payload.note):
        raise HTTPException(status_code=400, detail="attach tracking, url or note")

    order = await session.get(Order, order_id)
    if order is None or order.seller_id != seller.id:
        raise HTTPException(status_code=404, detail="order not found")
    if order.status not in ("paid", "fulfilled"):
        raise HTTPException(status_code=400, detail=f"order is {order.status}")

    order.fulfillment = payload.model_dump(exclude_none=True)
    order.status = "fulfilled"
    await session.commit()

    customer = await session.get(Customer, order.customer_id)
    bot_record = await session.get(SellerBot, customer.bot_id)

    from app.payments.service import _notify
    from app.security import decrypt_bot_token

    lines = [f"📦 Продавец отправил заказ #{order.id}!"]
    if payload.tracking:
        lines.append(f"Трек-номер: <code>{payload.tracking}</code>")
    if payload.url:
        lines.append(f"Ссылка: {payload.url}")
    if payload.note:
        lines.append(payload.note)
    await _notify(
        decrypt_bot_token(bot_record.bot_token_encrypted),
        customer.telegram_id,
        "\n".join(lines),
    )

    order.status = "delivered"
    await session.commit()

    payout = (
        await session.execute(select(Payout).where(Payout.order_id == order.id))
    ).scalar_one_or_none()
    if payout is not None:
        from app.payments.payouts import send_payout

        try:
            await send_payout(payout.id)
        except Exception:
            pass  # останется pending — ретрай подберёт

    return {"status": order.status}


class MailingIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    button_text: str | None = Field(default=None, max_length=64)
    button_url: str | None = Field(default=None, max_length=512)
    scheduled_at: str | None = None  # ISO-8601; null = отправить сразу


class MailingOut(BaseModel):
    id: int
    text: str
    status: str
    sent_count: int
    failed_count: int
    scheduled_at: object | None

    model_config = {"from_attributes": True}


@router.post("/mailings", response_model=MailingOut)
async def create_mailing(
    payload: MailingIn,
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> MailingOut:
    from datetime import datetime

    bot = (
        await session.execute(
            select(SellerBot).where(
                SellerBot.seller_id == seller.id, SellerBot.is_active.is_(True)
            )
        )
    ).scalars().first()
    if bot is None:
        raise HTTPException(status_code=400, detail="connect a bot first")
    if bool(payload.button_text) != bool(payload.button_url):
        raise HTTPException(status_code=400, detail="button needs both text and url")

    scheduled_at = None
    if payload.scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(payload.scheduled_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad scheduled_at")

    mailing = Mailing(
        seller_id=seller.id,
        bot_id=bot.id,
        text=payload.text,
        button_text=payload.button_text,
        button_url=payload.button_url,
        scheduled_at=scheduled_at,
    )
    session.add(mailing)
    await session.commit()
    return MailingOut.model_validate(mailing)


@router.get("/mailings", response_model=list[MailingOut])
async def list_mailings(
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> list[MailingOut]:
    result = await session.execute(
        select(Mailing).where(Mailing.seller_id == seller.id).order_by(Mailing.id.desc()).limit(50)
    )
    return [MailingOut.model_validate(m) for m in result.scalars().all()]


@router.get("/orders", response_model=list[SellerOrderOut])
async def list_orders(
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> list[SellerOrderOut]:
    result = await session.execute(
        select(Order, Customer)
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.seller_id == seller.id)
        .order_by(Order.id.desc())
        .limit(100)
    )
    return [
        SellerOrderOut(
            id=order.id,
            status=order.status,
            total=order.total,
            currency=order.currency,
            comment=order.comment,
            customer_username=customer.username,
            customer_first_name=customer.first_name,
        )
        for order, customer in result.all()
    ]
