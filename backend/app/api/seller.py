"""API кабинета продавца (Mini App открыт из hub-бота).

Ключевой принцип: один подключённый бот = один изолированный магазин.
Всё, что относится к магазину (каталог, заказы, покупатели, рассылки, статистика),
лежит под /seller/bots/{bot_id}/... и фильтруется по bot_id, а не по seller_id —
иначе данные магазинов одного продавца протекали бы друг в друга.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_seller
from app.db import get_api_session
from app.models import Customer, Mailing, Order, OrderItem, Payout, Product, Seller, SellerBot

router = APIRouter(prefix="/seller")

PRODUCT_TYPES = {"physical", "digital", "service"}


# --------------------------------------------------------------------------
# Профиль продавца и онбординг
# --------------------------------------------------------------------------


class BotOut(BaseModel):
    id: int
    bot_username: str
    webhook_status: str
    is_active: bool

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    onboarding_step: str  # payment_pending | payment_done | bot_pending | bot_done
    cryptobot_connected: bool
    commission_pct: Decimal
    plan: str
    is_admin: bool
    bots: list[BotOut]


async def _bots_of(session: AsyncSession, seller: Seller) -> list[SellerBot]:
    result = await session.execute(
        select(SellerBot).where(SellerBot.seller_id == seller.id).order_by(SellerBot.id)
    )
    return list(result.scalars().all())


def _me_payload(seller: Seller, bots: list[SellerBot]) -> MeOut:
    return MeOut(
        onboarding_step=seller.onboarding_step,
        cryptobot_connected=seller.cryptobot_connected,
        commission_pct=seller.commission_pct,
        plan=seller.plan,
        is_admin=seller.is_admin,
        bots=[BotOut.model_validate(b) for b in bots],
    )


@router.get("/me", response_model=MeOut)
async def me(
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> MeOut:
    """Первый запрос при открытии Mini App: по onboarding_step фронт понимает,
    какой экран рендерить, и не начинает онбординг заново после пересоздания webview."""
    return _me_payload(seller, await _bots_of(session, seller))


@router.post("/onboarding/payment-done", response_model=MeOut)
async def payment_done(
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> MeOut:
    """Шаг 1 пройден: продавец нажал /start у @CryptoBot.
    Реальная проверка — при первой выплате (Crypto Pay не даёт её заранее)."""
    seller.cryptobot_connected = True
    if seller.onboarding_step == "payment_pending":
        seller.onboarding_step = "bot_pending"
    await session.commit()
    return _me_payload(seller, await _bots_of(session, seller))


class ConnectBotIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ConnectBotOut(BaseModel):
    ok: bool
    error: str | None = None
    bot: BotOut | None = None


@router.post("/bots", response_model=ConnectBotOut)
async def connect_bot(
    payload: ConnectBotIn,
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> ConnectBotOut:
    """Шаг 2: подключение бота из Mini App. Токен валидируется через getMe,
    шифруется и сохраняется; вебхук регистрируется платформой."""
    from app.services.bot_connect import connect_seller_bot

    result = await connect_seller_bot(seller.id, payload.token)
    if not result.ok or result.bot_record is None:
        return ConnectBotOut(ok=False, error=result.error)
    return ConnectBotOut(ok=True, bot=BotOut.model_validate(result.bot_record))


# --------------------------------------------------------------------------
# Контекст магазина: всё ниже — только про один конкретный бот
# --------------------------------------------------------------------------


async def get_shop(
    bot_id: int = Path(),
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> SellerBot:
    bot = await session.get(SellerBot, bot_id)
    if bot is None or bot.seller_id != seller.id:
        raise HTTPException(status_code=404, detail="shop not found")
    return bot


class ShopSummaryOut(BaseModel):
    id: int
    bot_username: str
    is_active: bool
    webhook_status: str
    customers_count: int
    orders_count: int
    revenue: Decimal
    commission_pct: Decimal


@router.get("/bots/{bot_id}/summary", response_model=ShopSummaryOut)
async def shop_summary(
    shop: SellerBot = Depends(get_shop),
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> ShopSummaryOut:
    customers_count = (
        await session.execute(
            select(func.count()).select_from(Customer).where(Customer.bot_id == shop.id)
        )
    ).scalar_one()
    orders_count = (
        await session.execute(
            select(func.count()).select_from(Order).where(Order.bot_id == shop.id)
        )
    ).scalar_one()
    revenue = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.bot_id == shop.id,
                Order.status.in_(("paid", "fulfilled", "delivered")),
            )
        )
    ).scalar_one()
    return ShopSummaryOut(
        id=shop.id,
        bot_username=shop.bot_username,
        is_active=shop.is_active,
        webhook_status=shop.webhook_status,
        customers_count=customers_count,
        orders_count=orders_count,
        revenue=revenue,
        commission_pct=seller.commission_pct,
    )


# --------------------------------------------------------------------------
# Каталог магазина
# --------------------------------------------------------------------------


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


@router.get("/bots/{bot_id}/products", response_model=list[ProductOut])
async def list_products(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> list[ProductOut]:
    result = await session.execute(
        select(Product).where(Product.bot_id == shop.id).order_by(Product.id.desc())
    )
    return [ProductOut.model_validate(p) for p in result.scalars().all()]


@router.post("/bots/{bot_id}/products", response_model=ProductOut)
async def create_product(
    payload: ProductIn,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> ProductOut:
    if payload.type not in PRODUCT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(PRODUCT_TYPES)}")
    product = Product(seller_id=shop.seller_id, bot_id=shop.id, **payload.model_dump())
    session.add(product)
    await session.commit()
    return ProductOut.model_validate(product)


async def _shop_product(session: AsyncSession, shop: SellerBot, product_id: int) -> Product:
    product = await session.get(Product, product_id)
    if product is None or product.bot_id != shop.id:
        raise HTTPException(status_code=404, detail="product not found")
    return product


@router.put("/bots/{bot_id}/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductIn,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> ProductOut:
    if payload.type not in PRODUCT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(PRODUCT_TYPES)}")
    product = await _shop_product(session, shop, product_id)
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    await session.commit()
    return ProductOut.model_validate(product)


@router.delete("/bots/{bot_id}/products/{product_id}")
async def delete_product(
    product_id: int,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    product = await _shop_product(session, shop, product_id)
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


# --------------------------------------------------------------------------
# Заказы магазина
# --------------------------------------------------------------------------


class SellerOrderOut(BaseModel):
    id: int
    status: str
    total: Decimal
    currency: str
    comment: str | None
    customer_username: str | None
    customer_first_name: str | None


@router.get("/bots/{bot_id}/orders", response_model=list[SellerOrderOut])
async def list_orders(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> list[SellerOrderOut]:
    result = await session.execute(
        select(Order, Customer)
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.bot_id == shop.id)
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


class FulfillIn(BaseModel):
    tracking: str | None = Field(default=None, max_length=256)  # трек-номер
    url: str | None = Field(default=None, max_length=512)       # ссылка (файл/инвайт)
    note: str | None = Field(default=None, max_length=1000)     # координаты/примечание


@router.post("/bots/{bot_id}/orders/{order_id}/fulfill")
async def fulfill_order(
    order_id: int,
    payload: FulfillIn,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Продавец прикрепляет трек/ссылку/примечание -> бот пересылает покупателю,
    затем платформа отправляет продавцу его долю (Crypto Pay transfer)."""
    if not (payload.tracking or payload.url or payload.note):
        raise HTTPException(status_code=400, detail="attach tracking, url or note")

    order = await session.get(Order, order_id)
    if order is None or order.bot_id != shop.id:
        raise HTTPException(status_code=404, detail="order not found")
    if order.status not in ("paid", "fulfilled"):
        raise HTTPException(status_code=400, detail=f"order is {order.status}")

    order.fulfillment = payload.model_dump(exclude_none=True)
    order.status = "fulfilled"
    await session.commit()

    customer = await session.get(Customer, order.customer_id)

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
        decrypt_bot_token(shop.bot_token_encrypted),
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


# --------------------------------------------------------------------------
# Рассылки магазина
# --------------------------------------------------------------------------


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


@router.post("/bots/{bot_id}/mailings", response_model=MailingOut)
async def create_mailing(
    payload: MailingIn,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> MailingOut:
    from datetime import datetime

    if not shop.is_active:
        raise HTTPException(status_code=400, detail="bot is disconnected")
    if bool(payload.button_text) != bool(payload.button_url):
        raise HTTPException(status_code=400, detail="button needs both text and url")

    scheduled_at = None
    if payload.scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(payload.scheduled_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad scheduled_at")

    mailing = Mailing(
        seller_id=shop.seller_id,
        bot_id=shop.id,
        text=payload.text,
        button_text=payload.button_text,
        button_url=payload.button_url,
        scheduled_at=scheduled_at,
    )
    session.add(mailing)
    await session.commit()
    return MailingOut.model_validate(mailing)


@router.get("/bots/{bot_id}/mailings", response_model=list[MailingOut])
async def list_mailings(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> list[MailingOut]:
    result = await session.execute(
        select(Mailing).where(Mailing.bot_id == shop.id).order_by(Mailing.id.desc()).limit(50)
    )
    return [MailingOut.model_validate(m) for m in result.scalars().all()]
