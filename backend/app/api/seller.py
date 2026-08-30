"""API кабинета продавца (Mini App открыт из hub-бота).

Ключевой принцип: один подключённый бот = один изолированный магазин.
Всё, что относится к магазину (каталог, заказы, покупатели, рассылки, статистика),
лежит под /seller/bots/{bot_id}/... и фильтруется по bot_id, а не по seller_id —
иначе данные магазинов одного продавца протекали бы друг в друга.
"""

import html
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_seller
from app.config import get_settings
from app.db import get_api_session
from app.models import (
    ChatImage,
    ChatMessage,
    Customer,
    Mailing,
    Order,
    OrderChat,
    OrderItem,
    Product,
    ProductImage,
    ProductReview,
    Seller,
    SellerBot,
    ShopEvent,
    ShopLogo,
    StoreAdmin,
)
from app.models.orders import PAID_STATUSES
from app.payments.payouts import paid_total, pending_total
from app.plans import SERVICE_TYPES, is_pro, limits_for, over_limit
from app.services.images import MAX_IMAGE_BYTES, sniff_image_mime
from app.services.seller_texts import seller_text
from app.services.variants import apply_variants, line_title

router = APIRouter(prefix="/seller")

PRODUCT_TYPES = {"physical", "digital", "service"}


# --------------------------------------------------------------------------
# Профиль продавца и онбординг
# --------------------------------------------------------------------------


class BotOut(BaseModel):
    id: int
    # у черновика (магазин заведён, бот ещё нет) юзернейма не существует
    bot_username: str | None = None
    title: str | None = None
    is_draft: bool = False
    webhook_status: str
    is_active: bool

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    onboarding_step: str  # bot_pending | bot_done; payment_pending — legacy старых строк
    terms_accepted: bool
    # ставится по факту состоявшейся выплаты, а не со слов продавца
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
        terms_accepted=seller.terms_accepted_at is not None,
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


@router.post("/onboarding/terms-accept", response_model=MeOut)
async def terms_accept(
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> MeOut:
    """Продавец отметил принятие условий на первом экране онбординга.
    Фиксируем время один раз: повторный вызов не перетирает таймстамп."""
    if seller.terms_accepted_at is None:
        seller.terms_accepted_at = datetime.now(timezone.utc)
        await session.commit()
    return _me_payload(seller, await _bots_of(session, seller))


class ConnectBotIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ConnectBotOut(BaseModel):
    ok: bool
    error: str | None = None
    bot: BotOut | None = None


async def _notify_seller(seller: Seller, text: str, reply_markup=None) -> None:
    """Дубликат действия или события в чат с hub-ботом: Mini App может
    закрыться, а сообщение останется историей о магазине."""
    import logging

    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(seller.telegram_id, text, reply_markup=reply_markup)
    except Exception:
        logging.getLogger(__name__).exception(
            "Не удалось отправить уведомление продавцу %s", seller.id
        )


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

    # Кнопка ведёт сразу в кабинет этого магазина; без настроенного адреса
    # подтверждение уходит без неё
    kb = None
    webapp_url = get_settings().effective_webapp_url
    if webapp_url:
        from aiogram.types import WebAppInfo
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        ikb = InlineKeyboardBuilder()
        ikb.button(
            text=seller_text(seller, "btn.open_shop"),
            web_app=WebAppInfo(url=f"{webapp_url.rstrip('/')}/shop/{result.bot_record.id}"),
        )
        ikb.adjust(1)
        kb = ikb.as_markup()

    await _notify_seller(
        seller,
        seller_text(seller, "api.connected", username=result.bot_username),
        reply_markup=kb,
    )

    return ConnectBotOut(ok=True, bot=BotOut.model_validate(result.bot_record))


# --------------------------------------------------------------------------
# Контекст магазина: всё ниже — только про один конкретный бот
# --------------------------------------------------------------------------


async def get_shop(
    bot_id: int = Path(),
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> SellerBot:
    """Магазин для текущего продавца: владелец или приглашённый админ.

    Чужому отдаём ту же 404, что и несуществующему магазину, — сам факт его
    существования посторонним раскрывать не нужно.
    """
    bot = await session.get(SellerBot, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="shop not found")
    if bot.seller_id != seller.id:
        admin = (
            await session.execute(
                select(StoreAdmin).where(
                    StoreAdmin.bot_id == bot.id, StoreAdmin.seller_id == seller.id
                )
            )
        ).scalar_one_or_none()
        if admin is None:
            raise HTTPException(status_code=404, detail="shop not found")
    return bot


def _require_owner(shop: SellerBot, seller: Seller) -> None:
    """Деньги и необратимые действия магазина — только владельцу.

    Админ ведёт магазин наравне с владельцем (товары, заказы, рассылки,
    настройки), но выводит кассу не он, и магазин не он удаляет.
    """
    if shop.seller_id != seller.id:
        raise HTTPException(status_code=403, detail="owner only")


# --------------------------------------------------------------------------
# Управление магазином из приложения; каждое действие дублируется
# сообщением в hub-бот (см. _notify_seller)
# --------------------------------------------------------------------------


class ShopStateOut(BaseModel):
    id: int
    bot_username: str | None = None  # у черновика бота ещё нет
    is_active: bool


@router.post("/bots/{bot_id}/disable", response_model=ShopStateOut)
async def disable_shop(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> ShopStateOut:
    from app.services.bot_connect import disconnect_bot

    # админ тоже может включать/выключать; сервисы проверяют владельца —
    # подаём владельца магазина, а не того, кто нажал кнопку
    bot = await disconnect_bot(shop.id, shop.seller_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="shop not found")
    # уведомление — владельцу: действие мог совершить админ из его кабинета
    owner = await session.get(Seller, shop.seller_id)
    if owner is not None:
        await _notify_seller(
            owner,
            seller_text(owner, "api.disabled", username=bot.bot_username),
        )
    return ShopStateOut(id=bot.id, bot_username=bot.bot_username, is_active=False)


@router.post("/bots/{bot_id}/enable", response_model=ShopStateOut)
async def enable_shop(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> ShopStateOut:
    from app.services.bot_connect import enable_bot

    bot = await enable_bot(shop.id, shop.seller_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="shop not found")
    owner = await session.get(Seller, shop.seller_id)
    if owner is not None:
        await _notify_seller(
            owner,
            seller_text(owner, "api.enabled", username=bot.bot_username),
        )
    return ShopStateOut(id=bot.id, bot_username=bot.bot_username, is_active=True)


@router.delete("/bots/{bot_id}")
async def delete_shop(
    shop: SellerBot = Depends(get_shop),
    seller: Seller = Depends(get_seller),
) -> dict:
    # удаление необратимо и касается владельца, а не ведущего магазин
    _require_owner(shop, seller)
    from app.services.bot_connect import delete_bot

    result = await delete_bot(shop.id, seller.id)
    if result == "deleted":
        await _notify_seller(
            seller,
            seller_text(seller, "api.deleted", username=shop.bot_username),
        )
        return {"status": "deleted"}
    if result == "has_orders":
        await _notify_seller(
            seller,
            seller_text(seller, "api.has_orders", username=shop.bot_username),
        )
        return {"status": "has_orders"}
    raise HTTPException(status_code=404, detail="shop not found")


# --------------------------------------------------------------------------
# Идентичность магазина: показное имя и логотип шапки витрины
# --------------------------------------------------------------------------


class ShopNameIn(BaseModel):
    shop_name: str | None = Field(default=None, max_length=64)


@router.put("/bots/{bot_id}/shop-name")
async def set_shop_name(
    payload: ShopNameIn,
    shop: SellerBot = Depends(get_shop),
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Показное имя магазина в шапке витрины (дефолт — Telegram-имя бота).

    Пустая строка после strip — 422: сброс на дефолт передаётся null, чтобы
    случайная очистка поля не превращала витрину обратно в @username молча."""
    name = (payload.shop_name or "").strip()
    if payload.shop_name is not None and not name:
        raise HTTPException(status_code=422, detail="shop_name пуст — пришли null для сброса")
    shop.shop_name = name[:64] or None
    await session.commit()
    await _notify_seller(
        seller,
        seller_text(
            seller,
            "api.name_set" if shop.shop_name else "api.name_reset",
            name=html.escape(shop.shop_name or ""),
            username=html.escape(shop.bot_username or ""),
        ),
    )
    return {"shop_name": shop.shop_name}


@router.post("/bots/{bot_id}/shop-logo")
async def upload_shop_logo(
    request: Request,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Логотип магазина: сырые байты файла, тип по содержимому — как у фото
    товара. Старая строка удаляется целиком: адрес новой всегда другой, и
    immutable-кэш браузера не показывает старую картинку на её месте."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="фото больше 5 МБ")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="пустой файл")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="фото больше 5 МБ")
    mime = sniff_image_mime(data)
    if mime is None:
        raise HTTPException(status_code=400, detail="только JPEG, PNG, WebP или GIF")

    await session.execute(delete(ShopLogo).where(ShopLogo.bot_id == shop.id))
    logo = ShopLogo(bot_id=shop.id, mime=mime, size=len(data), data=data)
    session.add(logo)
    await session.commit()
    return {"url": f"/api/shop-logos/{logo.token}"}


@router.delete("/bots/{bot_id}/shop-logo")
async def remove_shop_logo(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Убрать лого — вернуться к первой букве имени вместо кружка."""
    await session.execute(delete(ShopLogo).where(ShopLogo.bot_id == shop.id))
    await session.commit()
    return {"status": "removed"}


# --------------------------------------------------------------------------
# Каналы магазина: список и отключение из кабинета.
# Подключение происходит в Telegram (бота добавляют админом), кабинет
# показывает картину и даёт отключить; владение проверяет get_shop.
# --------------------------------------------------------------------------


class ChannelOut(BaseModel):
    id: int
    title: str
    auto_accept: bool
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/bots/{bot_id}/channels", response_model=list[ChannelOut])
async def list_shop_channels(shop: SellerBot = Depends(get_shop)) -> list[ChannelOut]:
    from app.services.channels import list_channels

    return [ChannelOut.model_validate(ch) for ch in await list_channels(shop.id)]


@router.delete("/bots/{bot_id}/channels/{channel_id}")
async def remove_shop_channel(
    channel_id: int, shop: SellerBot = Depends(get_shop)
) -> dict:
    from app.services.channels import deactivate_channel_by_id

    if not await deactivate_channel_by_id(shop.id, channel_id):
        raise HTTPException(status_code=404, detail="channel not found")
    return {"status": "removed"}


class LimitsOut(BaseModel):
    """Использование против лимитов тарифа. Пока enforced=False лимиты
    только показываются; при включении они блокируют рост, но ничего
    не удаляют (см. app/plans.py)."""

    plan: str
    enforced: bool
    products_used: int
    products_cap: int | None
    services_used: int
    services_cap: int | None
    mailing_recipients_cap: int | None


class ShopSummaryOut(BaseModel):
    id: int
    bot_username: str
    # показное имя и лого шапки витрины — префилл панели идентичности кабинета
    shop_name: str | None = None
    logo_url: str | None = None
    is_active: bool
    webhook_status: str
    customers_count: int
    orders_count: int
    revenue: Decimal
    commission_pct: Decimal
    payout_pending: Decimal   # накоплено к выплате в этом магазине (баланс)
    payout_paid: Decimal      # уже выплачено этому магазину
    payout_min: Decimal       # минимум, с которого уходит перевод
    limits: LimitsOut
    # кто открыл кабинет: владелец видит кошелёк, админ — нет (денег касается
    # только владелец, поэтому фронт прячет wallet-карточку)
    viewer_role: str = "owner"


async def _catalog_usage(session: AsyncSession, bot_id: int) -> tuple[int, int]:
    """(товаров, услуг) в магазине — считаем и скрытые: они занимают место."""
    products_used = (
        await session.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.bot_id == bot_id, Product.type == "physical")
        )
    ).scalar_one()
    services_used = (
        await session.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.bot_id == bot_id, Product.type.in_(SERVICE_TYPES))
        )
    ).scalar_one()
    return products_used, services_used


async def _limits_payload(session: AsyncSession, seller: Seller, bot_id: int) -> LimitsOut:
    from app.config import get_settings

    limits = limits_for(seller)
    products_used, services_used = await _catalog_usage(session, bot_id)
    return LimitsOut(
        plan="pro" if is_pro(seller) else "free",
        enforced=get_settings().enforce_plan_limits,
        products_used=products_used,
        products_cap=limits.max_products,
        services_used=services_used,
        services_cap=limits.max_services,
        mailing_recipients_cap=limits.max_mailing_recipients,
    )


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
    logo = (
        await session.execute(select(ShopLogo).where(ShopLogo.bot_id == shop.id))
    ).scalar_one_or_none()
    # как в списке заказов и в выручке ниже: считаем только оплаченные —
    # корзины до оплаты и отменённые до оплаты цифру не растят
    orders_count = (
        await session.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.bot_id == shop.id, Order.status.in_(PAID_STATUSES))
        )
    ).scalar_one()
    revenue = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.bot_id == shop.id,
                Order.status.in_(PAID_STATUSES),
            )
        )
    ).scalar_one()
    return ShopSummaryOut(
        id=shop.id,
        bot_username=shop.bot_username,
        shop_name=shop.shop_name,
        logo_url=f"/api/shop-logos/{logo.token}" if logo else None,
        is_active=shop.is_active,
        webhook_status=shop.webhook_status,
        customers_count=customers_count,
        orders_count=orders_count,
        revenue=revenue,
        commission_pct=seller.commission_pct,
        payout_pending=await pending_total(session, shop.id),
        payout_paid=await paid_total(session, shop.id),
        payout_min=Decimal(str(get_settings().min_payout_usdt)),
        limits=await _limits_payload(session, seller, shop.id),
        viewer_role="owner" if shop.seller_id == seller.id else "admin",
    )


class WithdrawOut(BaseModel):
    ok: bool                 # ушёл ли перевод этим вызовом
    sent: Decimal            # сколько ушло (0, если не ушло)
    pending: Decimal         # сколько осталось накоплено после попытки
    minimum: Decimal
    # no_funds | below_min | no_token | cryptobot_not_started | too_small | failed
    reason: str | None


@router.post("/bots/{bot_id}/payouts/withdraw", response_model=WithdrawOut)
async def withdraw(
    shop: SellerBot = Depends(get_shop),
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> WithdrawOut:
    """Забрать накопленное этим магазином.

    Только владелец: админ видит магазин, но не кассу (см. _require_owner).

    Касса у каждого бота своя, поэтому кнопка выводит деньги только своего
    магазина; повторное нажатие не задваивает перевод (идемпотентный spend_id).

    Готовность @CryptoBot заранее не спрашиваем: API проверить это не умеет,
    а сама попытка перевода отвечает точно. Если бот не открыт, вернётся
    reason=cryptobot_not_started, и приложение покажет этот шаг.
    """
    _require_owner(shop, seller)
    from app.payments.client import get_crypto_pay
    from app.payments.payouts import flush_shop_payouts

    minimum = Decimal(str(get_settings().min_payout_usdt))
    before = await pending_total(session, shop.id)
    if before <= 0:
        return WithdrawOut(
            ok=False, sent=Decimal(0), pending=before, minimum=minimum, reason="no_funds"
        )
    if before < minimum:
        return WithdrawOut(
            ok=False, sent=Decimal(0), pending=before, minimum=minimum, reason="below_min"
        )
    if get_crypto_pay() is None:
        # оплата не настроена на стороне платформы — это не вина продавца
        return WithdrawOut(
            ok=False, sent=Decimal(0), pending=before, minimum=minimum, reason="no_token"
        )

    result = await flush_shop_payouts(shop.id)
    after = await pending_total(session, shop.id)
    return WithdrawOut(
        ok=result.ok,
        sent=before - after if result.ok else Decimal(0),
        pending=after,
        minimum=minimum,
        reason=result.reason,
    )


# --------------------------------------------------------------------------
# Статистика магазина
# --------------------------------------------------------------------------


class ShopStatsOut(BaseModel):
    telegram_users: int      # покупателей в базе этого бота
    product_views: int       # просмотры карточек товара
    checkout_starts: int     # открытий оформления заказа
    purchases: int           # оплаченные заказы
    total_sales: Decimal     # сумма оплаченных заказов
    repeat_customers: int    # покупатели с двумя и более покупками


async def _count_events(session: AsyncSession, bot_id: int, event_type: str) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(ShopEvent)
            .where(ShopEvent.bot_id == bot_id, ShopEvent.type == event_type)
        )
    ).scalar_one()


@router.get("/bots/{bot_id}/stats", response_model=ShopStatsOut)
async def shop_stats(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> ShopStatsOut:
    telegram_users = (
        await session.execute(
            select(func.count()).select_from(Customer).where(Customer.bot_id == shop.id)
        )
    ).scalar_one()
    purchases = (
        await session.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.bot_id == shop.id, Order.status.in_(PAID_STATUSES))
        )
    ).scalar_one()
    total_sales = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.bot_id == shop.id, Order.status.in_(PAID_STATUSES)
            )
        )
    ).scalar_one()
    # повторные: покупатели, у которых больше одной оплаченной покупки
    repeat_customers = (
        await session.execute(
            select(func.count()).select_from(
                select(Order.customer_id)
                .where(Order.bot_id == shop.id, Order.status.in_(PAID_STATUSES))
                .group_by(Order.customer_id)
                .having(func.count(Order.id) > 1)
                .subquery()
            )
        )
    ).scalar_one()

    return ShopStatsOut(
        telegram_users=telegram_users,
        product_views=await _count_events(session, shop.id, "product_view"),
        checkout_starts=await _count_events(session, shop.id, "checkout_start"),
        purchases=purchases,
        total_sales=total_sales,
        repeat_customers=repeat_customers,
    )


# --------------------------------------------------------------------------
# Каталог магазина
# --------------------------------------------------------------------------


@router.post("/bots/{bot_id}/product-image")
async def upload_product_image(
    request: Request,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Фото товара грузится сырыми байтами, без multipart. Тип определяем
    по содержимому (сниффер магических байтов) — content-type и имя файла
    от клиента не учитываются."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="фото больше 5 МБ")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="пустой файл")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="фото больше 5 МБ")
    mime = sniff_image_mime(data)
    if mime is None:
        raise HTTPException(status_code=400, detail="только JPEG, PNG, WebP или GIF")
    image = ProductImage(bot_id=shop.id, mime=mime, size=len(data), data=data)
    session.add(image)
    await session.commit()
    return {"id": image.id, "url": f"/api/images/{image.token}"}


class VariantIn(BaseModel):
    """Вариация в запросе сохранения товара. `id` есть у уже существующих."""

    id: int | None = None
    sku: str | None = Field(default=None, max_length=64)
    attributes: dict[str, str] | None = None
    # Своё название и описание; None — берётся товарное
    title: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal = Field(gt=0)
    # зачёркнутая «старая» цена; должна быть выше текущей, иначе это не скидка
    compare_at_price: Decimal | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0, le=1_000_000)
    images: list[str] | None = None
    is_active: bool = True


class VariantOut(VariantIn):
    id: int

    model_config = {"from_attributes": True}


class ProductIn(BaseModel):
    type: str
    title: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, max_length=512)
    price: Decimal = Field(gt=0)
    # зачёркнутая «старая» цена самого товара; у товара с вариациями скидка
    # живёт на вариации, и это поле обнуляется пересчётом
    compare_at_price: Decimal | None = Field(default=None, gt=0)
    # остаток на складе; None — не ограничен (услуги/digital без учёта штук)
    stock: int | None = Field(default=None, ge=0, le=1_000_000)
    digital_content: dict | None = None
    is_active: bool = True
    # None — вариации в запросе не участвуют (старый клиент их не сотрёт);
    # пустой список — у товара их больше нет
    variants: list[VariantIn] | None = None


class ProductOut(ProductIn):
    id: int
    currency: str
    variants: list[VariantOut] = []

    model_config = {"from_attributes": True}


@router.get("/bots/{bot_id}/products", response_model=list[ProductOut])
async def list_products(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> list[ProductOut]:
    # selectinload обязателен: без него model_validate дёрнет ленивую загрузку
    # вариаций уже вне сессии и упадёт на MissingGreenlet
    result = await session.execute(
        select(Product)
        .options(selectinload(Product.variants))
        .where(Product.bot_id == shop.id)
        .order_by(Product.id.desc())
    )
    return [ProductOut.model_validate(p) for p in result.scalars().all()]


def _check_pricing(payload: "ProductIn") -> None:
    """Вариации есть только у физических товаров: у услуги или файла нет ни
    размера, ни цвета, а цена и остаток живут на самом товаре.

    Здесь же — единственная проверка «старой» цены: зачёркнутое число обязано
    быть выше текущего, иначе это не скидка, а обман покупателя. Проверяем и
    товар, и каждую вариацию: правило одно, а мест ввода два.
    """
    variants = payload.variants or []
    if variants and payload.type != "physical":
        raise HTTPException(
            status_code=400, detail="variants are only available for physical products"
        )
    for item in [payload, *variants]:
        if item.compare_at_price is not None and item.compare_at_price <= item.price:
            raise HTTPException(
                status_code=422,
                detail="compare_at_price must be higher than price",
            )


@router.post("/bots/{bot_id}/products", response_model=ProductOut)
async def create_product(
    payload: ProductIn,
    shop: SellerBot = Depends(get_shop),
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> ProductOut:
    if payload.type not in PRODUCT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(PRODUCT_TYPES)}")

    from app.config import get_settings

    if get_settings().enforce_plan_limits:
        limits = limits_for(seller)
        products_used, services_used = await _catalog_usage(session, shop.id)
        is_service = payload.type in SERVICE_TYPES
        used = services_used if is_service else products_used
        cap = limits.max_services if is_service else limits.max_products
        if over_limit(used, cap):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"plan limit reached: {cap} "
                    f"{'услуг' if is_service else 'товаров'} на бесплатном тарифе"
                ),
            )

    _check_pricing(payload)
    fields = payload.model_dump(exclude={"variants"})
    product = Product(seller_id=shop.seller_id, bot_id=shop.id, **fields)
    session.add(product)
    await session.flush()  # нужен product.id, чтобы привязать вариации
    await apply_variants(session, product, payload.variants)
    await session.commit()
    await session.refresh(product, ["variants"])
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
    _check_pricing(payload)
    product = await _shop_product(session, shop, product_id)
    await session.refresh(product, ["variants"])
    for key, value in payload.model_dump(exclude={"variants"}).items():
        setattr(product, key, value)
    await apply_variants(session, product, payload.variants)
    await session.commit()
    await session.refresh(product, ["variants"])
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


class SellerOrderItemOut(BaseModel):
    """Состав заказа: названия берутся из каталога, цена — зафиксированная
    на момент покупки из OrderItem (каталог мог подорожать после)."""

    product_id: int
    title: str
    # чем строка отличается от соседней с тем же товаром — «Красный · M»
    variant_label: str | None = None
    qty: int
    price: Decimal


class SellerOrderOut(BaseModel):
    """Без данных покупателя: сервис анонимный, продавцу достаточно заказа —
    личность раскрывается только в relay-чате и только как роль отправителя."""

    id: int
    status: str
    total: Decimal
    currency: str
    comment: str | None
    created_at: datetime
    items: list[SellerOrderItemOut]
    # то, что продавец отправил покупателю при выполнении (трек/ссылка/note)
    fulfillment: dict | None = None
    # куда везти: {name, phone, address}. Единственные данные покупателя,
    # которые видит продавец, и только у физических заказов — без них
    # отправить посылку физически нельзя
    delivery: dict | None = None


@router.get("/bots/{bot_id}/orders", response_model=list[SellerOrderOut])
async def list_orders(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> list[SellerOrderOut]:
    result = await session.execute(
        select(Order)
        .where(
            Order.bot_id == shop.id,
            # рабочий список начинается с момента оплаты: неоплаченные корзины
            # и заказы, отменённые покупателем до оплаты, не показываются.
            # Отменённым может стать только неоплаченный — «lost» статусов нет
            Order.status.notin_(("pending_payment", "cancelled")),
        )
        .order_by(Order.id.desc())
        .limit(100)
    )
    orders = result.scalars().all()
    # состав всех заказов одним запросом, чтобы не ходить в БД за каждым
    items_by_order: dict[int, list[SellerOrderItemOut]] = {}
    if orders:
        items_result = await session.execute(
            select(OrderItem, Product.title)
            .join(Product, Product.id == OrderItem.product_id)
            .where(OrderItem.order_id.in_([o.id for o in orders]))
        )
        for item, title in items_result.all():
            items_by_order.setdefault(item.order_id, []).append(
                SellerOrderItemOut(
                    product_id=item.product_id,
                    title=line_title(title, item.variant_title),
                    variant_label=item.variant_label,
                    qty=item.qty,
                    price=item.price,
                )
            )
    return [
        SellerOrderOut(
            id=order.id,
            status=order.status,
            total=order.total,
            currency=order.currency,
            comment=order.comment,
            created_at=order.created_at,
            items=items_by_order.get(order.id, []),
            fulfillment=order.fulfillment,
            delivery=order.delivery,
        )
        for order in orders
    ]


# --------------------------------------------------------------------------
# Отзывы о товарах магазина: только чтение, автор не раскрывается
# --------------------------------------------------------------------------


class SellerReviewOut(BaseModel):
    id: int
    # заказ, к которому относится отзыв: продавцу видно, о какой покупке речь
    order_id: int
    product_title: str
    # имя автора — то же, что видят покупатели на странице товара
    author_name: str | None
    rating: int
    body: str | None
    # published | pending | rejected: ожидающие ждут одобрения во вкладке
    # «Отзывы», отклонённые видны только здесь же, с возможностью вернуть
    status: str
    moderated_at: datetime | None
    reply_body: str | None
    reply_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


@router.get("/bots/{bot_id}/reviews", response_model=list[SellerReviewOut])
async def list_reviews(
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> list[SellerReviewOut]:
    result = await session.execute(
        select(ProductReview, Product.title)
        .join(Product, Product.id == ProductReview.product_id)
        .where(ProductReview.bot_id == shop.id)
        .order_by(ProductReview.id.desc())
        .limit(50)
    )
    return [
        SellerReviewOut(
            id=review.id,
            order_id=review.order_id,
            product_title=title,
            author_name=review.author_name,
            rating=review.rating,
            body=review.body,
            status=review.status,
            moderated_at=review.moderated_at,
            reply_body=review.reply_body,
            reply_at=review.reply_at,
            created_at=review.created_at,
        )
        for review, title in result.all()
    ]


def _review_out(review: ProductReview, product_title: str) -> SellerReviewOut:
    return SellerReviewOut(
        id=review.id,
        order_id=review.order_id,
        product_title=product_title,
        author_name=review.author_name,
        rating=review.rating,
        body=review.body,
        status=review.status,
        moderated_at=review.moderated_at,
        reply_body=review.reply_body,
        reply_at=review.reply_at,
        created_at=review.created_at,
    )


@router.post("/bots/{bot_id}/reviews/{review_id}/approve", response_model=SellerReviewOut)
async def approve_review(
    review_id: int,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> SellerReviewOut:
    """Одобрить отзыв на проверке: он публикуется и идёт в рейтинги."""
    review = await _own_review(session, shop, review_id)
    if review.status == "published":
        return _review_out(review, await _review_product_title(session, review))
    review.status = "published"
    review.moderated_at = func.now()
    await session.commit()
    await session.refresh(review)
    return _review_out(review, await _review_product_title(session, review))


@router.post("/bots/{bot_id}/reviews/{review_id}/reject", response_model=SellerReviewOut)
async def reject_review(
    review_id: int,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> SellerReviewOut:
    """Отклонить отзыв: из рейтингов и публичных списков он исчезает. Правка
    покупателем возвращает его на проверку, сам он не публикуется."""
    review = await _own_review(session, shop, review_id)
    if review.status == "rejected":
        return _review_out(review, await _review_product_title(session, review))
    review.status = "rejected"
    review.moderated_at = func.now()
    await session.commit()
    await session.refresh(review)
    return _review_out(review, await _review_product_title(session, review))


async def _own_review(
    session: AsyncSession, shop: SellerBot, review_id: int
) -> ProductReview:
    review = await session.get(ProductReview, review_id)
    if review is None or review.bot_id != shop.id:
        raise HTTPException(status_code=404, detail="review not found")
    return review


async def _review_product_title(session: AsyncSession, review: ProductReview) -> str:
    product = await session.get(Product, review.product_id)
    return product.title if product else ""


@router.post("/bots/{bot_id}/reviews/{review_id}/reply", response_model=SellerReviewOut)
async def reply_to_review(
    review_id: int,
    payload: ReviewReplyIn,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> SellerReviewOut:
    """Ответ продавца на отзыв. Один на отзыв; повторная отправка правит его."""
    review = await _own_review(session, shop, review_id)

    review.reply_body = payload.body
    review.reply_at = func.now()
    await session.commit()
    await session.refresh(review)

    return _review_out(review, await _review_product_title(session, review))


class FulfillIn(BaseModel):
    # Единое поле «что отправлено» — трек-номер или ссылка; прежние три поля
    # (tracking/url/note) схлопнулись в одно по мокапу владельца.
    value: str | None = Field(default=None, max_length=512)
    # Сколько фото продавец приложил сверх текста. Сам эндпоинт фото не
    # принимает: фронт шлёт их через POST .../chat/photo уже после успешного
    # fulfill — там готовая доставка покупателю и история чата. Число нужно,
    # чтобы можно было отправить только фото без единой строки текста.
    photos: int = Field(default=0, ge=0, le=3)


@router.post("/bots/{bot_id}/orders/{order_id}/fulfill")
async def fulfill_order(
    order_id: int,
    payload: FulfillIn,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """Продавец прикрепляет трек/ссылку/фото -> бот пересылает покупателю.
    Доля продавца остаётся в кассе магазина — вывод только по кнопке «Вывести»."""
    value = (payload.value or "").strip()
    if not (value or payload.photos):
        raise HTTPException(status_code=400, detail="attach tracking, link or photo")

    order = await session.get(Order, order_id)
    if order is None or order.bot_id != shop.id:
        raise HTTPException(status_code=404, detail="order not found")
    if order.status not in ("paid", "fulfilled"):
        raise HTTPException(status_code=400, detail=f"order is {order.status}")

    fulfillment: dict = {"photos": payload.photos}
    if value:
        fulfillment["value"] = value[:512]
    order.fulfillment = fulfillment
    # «Отправлен», а не «Доставлен»: посылка едет днями, а от delivered_at
    # тикает окно чата. Раньше покупатель видел «Доставлен» в первый же день,
    # а на четвёртый, когда посылка потерялась, писать продавцу было уже
    # нельзя. «Доставлен» ставит сам покупатель кнопкой «Получил» — или
    # фоновая задача, если он про неё забыл (app/services/order_health.py).
    order.status = "fulfilled"
    await session.commit()

    customer = await session.get(Customer, order.customer_id)

    # отправка остаётся в истории чата заказа: продавец в кабинете видит, что
    # и куда отправил (фото прикладывались бы следом отдельными сообщениями).
    # Запись служебная и не должна сорвать отправку — падение гасим.
    # Текст — на языке покупателя: чат заказа читают обе стороны, а покупателю
    # он ближе (продавец видит то же самое строкой в карточке заказа, на своём).
    from app.services.chat import add_service_note, get_or_create_chat
    from app.services.notify_texts import buyer_text

    note_lines = [buyer_text(customer, "note.sent", id=order.id)]
    if value:
        note_lines.append(value[:512])
    elif payload.photos == 1:
        note_lines.append(buyer_text(customer, "fulfill.photo_one"))
    elif payload.photos:
        note_lines.append(buyer_text(customer, "fulfill.photo_many", n=payload.photos))
    chat = await get_or_create_chat(session, order)
    if chat is not None:
        try:
            async with session.begin_nested():
                await add_service_note(session, chat, order, "\n".join(note_lines))
            await session.commit()
        except Exception:
            pass  # журнал не критичен: заказ уже отправлен, пуш уйдёт ниже

    from app.payments.service import _notify
    from app.security import decrypt_bot_token

    # текст продавца уходит с parse_mode=HTML — экранируем, иначе «<» в
    # примечании или треке оставит покупателя без уведомления об отправке
    lines = [buyer_text(customer, "fulfill.header", id=order.id)]
    if value:
        lines.append(html.escape(value))
    elif payload.photos == 1:
        lines.append(buyer_text(customer, "fulfill.photo_one"))
    elif payload.photos:
        lines.append(buyer_text(customer, "fulfill.photo_many", n=payload.photos))
    lines.append("\n" + buyer_text(customer, "fulfill.hint"))
    await _notify(
        decrypt_bot_token(shop.bot_token_encrypted),
        customer.telegram_id,
        "\n".join(lines),
    )

    return {"status": order.status}


# --------------------------------------------------------------------------
# Чат заказа: продавец <-> покупатель через relay (личности не раскрываются)
# --------------------------------------------------------------------------


class ChatMessageOut(BaseModel):
    id: int
    sender: str  # seller | customer
    body: str
    image_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderChatOut(BaseModel):
    status: str  # active | locked_by_timeout | archived
    can_send: bool
    closes_at: datetime | None
    messages: list[ChatMessageOut]


class ChatMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


async def _order_with_chat(
    shop: SellerBot, order_id: int, session: AsyncSession
) -> tuple[Order, OrderChat]:
    """Заказ и его чат в контексте магазина. Чужой заказ или неоплаченный —
    403: подменённый id не должен даже намекать на существование переписки."""
    from app.services.chat import get_or_create_chat

    order = await session.get(Order, order_id)
    if order is None or order.bot_id != shop.id:
        raise HTTPException(status_code=403, detail="foreign order")
    chat = await get_or_create_chat(session, order)
    if chat is None:
        raise HTTPException(status_code=403, detail="chat_not_available")
    return order, chat


@router.get("/bots/{bot_id}/orders/{order_id}/chat", response_model=OrderChatOut)
async def get_order_chat(
    order_id: int,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> OrderChatOut:
    """История переписки по заказу + состояние окна активности."""
    from app.services.chat import chat_is_open, closes_at, read_history

    order, chat = await _order_with_chat(shop, order_id, session)
    messages = await read_history(session, chat.id)
    await session.commit()  # чат мог создаться этим вызовом
    return OrderChatOut(
        status=chat.status,
        can_send=chat_is_open(order),
        closes_at=closes_at(order),
        messages=[ChatMessageOut.model_validate(m) for m in messages],
    )


@router.post("/bots/{bot_id}/orders/{order_id}/chat/messages", response_model=ChatMessageOut)
async def send_order_chat_message(
    order_id: int,
    payload: ChatMessageIn,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> ChatMessageOut:
    """Сообщение продавца: пишем в базу, доставляем покупателю от бота магазина."""
    from app.db import session_factory
    from app.services.chat import (
        ChatLockedError,
        RateLimitedError,
        notify_customer,
        send_message,
    )
    from app.services.notify_texts import buyer_locale

    order, chat = await _order_with_chat(shop, order_id, session)
    try:
        message = await send_message(session, chat, order, "seller", payload.body)
    except ChatLockedError:
        raise HTTPException(status_code=403, detail="chat_locked")
    except RateLimitedError:
        raise HTTPException(status_code=429, detail="too_many_messages")

    out = ChatMessageOut.model_validate(message)
    customer = await session.get(Customer, order.customer_id)
    await session.commit()

    # Доставка после коммита: сбой Telegram не должен терять сообщение из
    # истории (продавец увидит его в кабинете при следующем открытии).
    # Обёртка «💬 Заказ #N» — на языке покупателя.
    tg_message_id = await notify_customer(
        shop, customer.telegram_id, order.id, message.body, locale=buyer_locale(customer)
    )
    if tg_message_id is not None:
        async with session_factory() as followup:
            await followup.execute(
                update(ChatMessage)
                .where(ChatMessage.id == out.id)
                .values(tg_message_id=tg_message_id)
            )
            await followup.commit()
    return out


@router.post("/bots/{bot_id}/orders/{order_id}/chat/photo", response_model=ChatMessageOut)
async def send_order_chat_photo(
    order_id: int,
    request: Request,
    caption: str | None = None,
    shop: SellerBot = Depends(get_shop),
    session: AsyncSession = Depends(get_api_session),
) -> ChatMessageOut:
    """Фото продавца в чат заказа: сырые байты (как у фото товара), подпись —
    query-параметром. Пишем в историю, доставляем покупателю от бота магазина."""
    from app.db import session_factory
    from app.services.chat import (
        ChatLockedError,
        RateLimitedError,
        notify_customer_photo,
        send_message,
    )
    from app.services.notify_texts import buyer_locale

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="фото больше 5 МБ")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="пустой файл")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="фото больше 5 МБ")
    mime = sniff_image_mime(data)
    if mime is None:
        raise HTTPException(status_code=400, detail="только JPEG, PNG, WebP или GIF")

    order, chat = await _order_with_chat(shop, order_id, session)
    image = ChatImage(bot_id=shop.id, chat_id=chat.id, mime=mime, size=len(data), data=data)
    session.add(image)
    await session.flush()

    try:
        message = await send_message(
            session, chat, order, "seller", caption or "", image_token=image.token
        )
    except ChatLockedError:
        raise HTTPException(status_code=403, detail="chat_locked")
    except RateLimitedError:
        raise HTTPException(status_code=429, detail="too_many_messages")

    out = ChatMessageOut.model_validate(message)
    customer = await session.get(Customer, order.customer_id)
    await session.commit()

    # Доставка после коммита — как у текстовых сообщений: сбой Telegram не
    # теряет фото из истории кабинета. Обёртка — на языке покупателя.
    tg_message_id = await notify_customer_photo(
        shop,
        customer.telegram_id,
        order.id,
        data,
        mime,
        message.body or None,
        locale=buyer_locale(customer),
    )
    if tg_message_id is not None:
        async with session_factory() as followup:
            await followup.execute(
                update(ChatMessage)
                .where(ChatMessage.id == out.id)
                .values(tg_message_id=tg_message_id)
            )
            await followup.commit()
    return out


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
    scheduled_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("/bots/{bot_id}/mailings", response_model=MailingOut)
async def create_mailing(
    payload: MailingIn,
    shop: SellerBot = Depends(get_shop),
    seller: Seller = Depends(get_seller),
    session: AsyncSession = Depends(get_api_session),
) -> MailingOut:
    from datetime import datetime

    from app.config import get_settings

    if not shop.is_active:
        raise HTTPException(status_code=400, detail="bot is disconnected")

    if get_settings().enforce_plan_limits:
        cap = limits_for(seller).max_mailing_recipients
        if cap is not None:
            recipients = (
                await session.execute(
                    select(func.count())
                    .select_from(Customer)
                    .where(
                        Customer.bot_id == shop.id,
                        Customer.is_banned.is_(False),
                        # тем, у кого бот заблокирован, рассылка всё равно не
                        # уйдёт — в лимит тарифа они не считаются
                        Customer.mailing_blocked.is_(False),
                    )
                )
            ).scalar_one()
            if recipients > cap:
                # база остаётся целой — блокируется только отправка сверх лимита
                raise HTTPException(
                    status_code=403,
                    detail=f"plan limit reached: рассылка до {cap} получателей на бесплатном тарифе",
                )
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
