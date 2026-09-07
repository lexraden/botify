"""Сводка по всей платформе для админа (hub-бот, /stats).

Ничего не считает заново: все числа выводятся из уже существующих строк —
продавцов, магазинов, товаров, заказов и пачек выплат. Отдельной таблицы
метрик нет намеренно, иначе она разъедется с источником при первом же
исправлении данных.

Воронка продавца тоже собирается отсюда, а не из событий: событий про
продавца никто не пишет, но факт «дошёл до этого шага» виден по наличию
строки. Чего так не узнать — когда именно человек отвалился и почему;
для этого нужны события, и завести их можно только на будущее.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Customer, Order, PayoutBatch, Product, Seller, SellerBot
from app.models.orders import PAID_STATUSES


@dataclass(frozen=True)
class Totals:
    sellers: int
    shops: int          # всего строк магазинов, включая черновики
    shops_live: int     # с подключённым ботом и включённые
    customers: int
    products: int


@dataclass(frozen=True)
class Funnel:
    """Сколько продавцов дошло до каждого шага. Шаги вложены: у дошедшего до
    продажи обязательно есть и бот, и товар."""

    registered: int
    with_shop: int
    with_bot: int
    with_product: int
    with_sale: int
    with_payout: int


@dataclass(frozen=True)
class Sales:
    orders: int
    gmv: Decimal
    gmv_30d: Decimal
    gmv_7d: Decimal

    @property
    def avg_check(self) -> Decimal:
        return (self.gmv / self.orders).quantize(Decimal("0.01")) if self.orders else Decimal(0)


@dataclass(frozen=True)
class ShopRow:
    bot_id: int
    name: str
    orders: int
    gmv: Decimal


async def _count(session, stmt) -> int:
    return (await session.execute(stmt)).scalar_one() or 0


async def totals(session) -> Totals:
    return Totals(
        sellers=await _count(session, select(func.count()).select_from(Seller)),
        shops=await _count(session, select(func.count()).select_from(SellerBot)),
        shops_live=await _count(
            session,
            select(func.count())
            .select_from(SellerBot)
            .where(SellerBot.bot_token_encrypted.is_not(None), SellerBot.is_active.is_(True)),
        ),
        customers=await _count(session, select(func.count()).select_from(Customer)),
        products=await _count(session, select(func.count()).select_from(Product)),
    )


async def funnel(session) -> Funnel:
    async def distinct_sellers(model, *where) -> int:
        return await _count(
            session, select(func.count(func.distinct(model.seller_id))).where(*where)
        )

    return Funnel(
        registered=await _count(session, select(func.count()).select_from(Seller)),
        with_shop=await distinct_sellers(SellerBot),
        with_bot=await distinct_sellers(SellerBot, SellerBot.bot_token_encrypted.is_not(None)),
        with_product=await distinct_sellers(Product),
        with_sale=await distinct_sellers(Order, Order.status.in_(PAID_STATUSES)),
        with_payout=await distinct_sellers(PayoutBatch, PayoutBatch.status == "sent"),
    )


async def sales(session) -> Sales:
    now = datetime.now(timezone.utc)

    async def gmv_since(cutoff: datetime | None) -> Decimal:
        stmt = select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.status.in_(PAID_STATUSES)
        )
        if cutoff is not None:
            stmt = stmt.where(Order.paid_at >= cutoff)
        return Decimal(str((await session.execute(stmt)).scalar_one() or 0))

    return Sales(
        orders=await _count(
            session,
            select(func.count()).select_from(Order).where(Order.status.in_(PAID_STATUSES)),
        ),
        gmv=await gmv_since(None),
        gmv_30d=await gmv_since(now - timedelta(days=30)),
        gmv_7d=await gmv_since(now - timedelta(days=7)),
    )


async def top_shops(session, limit: int = 10) -> list[ShopRow]:
    """Магазины по обороту оплаченных заказов, от большего.

    Имя берём то же, что видит покупатель в шапке витрины: shop_name, иначе
    название из /newshop, иначе юзернейм бота. Иначе в списке оказались бы
    строки «магазин #7», по которым непонятно, о ком речь.
    """
    rows = (
        await session.execute(
            select(
                SellerBot.id,
                SellerBot.shop_name,
                SellerBot.title,
                SellerBot.bot_username,
                func.count(Order.id),
                func.coalesce(func.sum(Order.total), 0),
            )
            .join(Order, Order.bot_id == SellerBot.id)
            .where(Order.status.in_(PAID_STATUSES))
            .group_by(SellerBot.id)
            .order_by(func.sum(Order.total).desc())
            .limit(limit)
        )
    ).all()
    return [
        ShopRow(
            bot_id=bot_id,
            name=shop_name or title or (f"@{username}" if username else f"#{bot_id}"),
            orders=orders,
            gmv=Decimal(str(gmv)),
        )
        for bot_id, shop_name, title, username, orders, gmv in rows
    ]
