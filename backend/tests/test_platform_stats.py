"""Сводка по платформе для админа (/stats).

Проверяются числа, а не форма сообщения: сводка нужна для решений, и
ошибка здесь — это неверная картина бизнеса, а не косметика.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Order, PayoutBatch, Seller, SellerBot
from app.payments.service import handle_invoice_paid
from app.services import platform_stats
from tests.test_payments import make_order, patched_notifications


async def _pay(db, invoice_id=555001):
    p1, p2 = patched_notifications()
    with p1, p2:
        assert await handle_invoice_paid(invoice_id, None) is True


@pytest.mark.asyncio
async def test_empty_platform_reports_zeros(db):
    """Свежая база не должна ронять сводку и не должна врать про оборот."""
    async with db() as session:
        assert (await platform_stats.totals(session)).sellers == 0
        assert (await platform_stats.sales(session)).gmv == 0
        assert (await platform_stats.sales(session)).avg_check == 0
        assert await platform_stats.top_shops(session) == []


@pytest.mark.asyncio
async def test_totals_and_sales_count_only_paid(db):
    await make_order(db, invoice_id=555001, total=Decimal("100"))
    await make_order(db, invoice_id=555002, total=Decimal("40"))
    await _pay(db, 555001)  # оплачен только первый

    async with db() as session:
        t = await platform_stats.totals(session)
        s = await platform_stats.sales(session)

    assert t.sellers == 1 and t.shops == 1 and t.shops_live == 1
    assert t.customers == 1 and t.products == 2
    # неоплаченный заказ в оборот не входит: денег по нему не было
    assert s.orders == 1
    assert s.gmv == Decimal(100)
    assert s.gmv_30d == Decimal(100) and s.gmv_7d == Decimal(100)
    assert s.avg_check == Decimal("100.00")


@pytest.mark.asyncio
async def test_funnel_steps_are_nested(db):
    """Дошедший до продажи обязан числиться и в предыдущих шагах."""
    await make_order(db, invoice_id=555001, total=Decimal("100"))

    async with db() as session:
        before = await platform_stats.funnel(session)
    assert before.registered == 1
    assert before.with_shop == 1 and before.with_bot == 1 and before.with_product == 1
    assert before.with_sale == 0  # ещё не оплачен
    assert before.with_payout == 0

    await _pay(db, 555001)
    async with db() as session:
        after = await platform_stats.funnel(session)
    assert after.with_sale == 1
    assert after.with_payout == 0  # выплата начислена, но не отправлена


@pytest.mark.asyncio
async def test_funnel_counts_sellers_once_not_shops(db):
    """У продавца может быть несколько магазинов — в воронке он один."""
    await make_order(db, invoice_id=555001, total=Decimal("10"))
    async with db() as session:
        seller = (await session.execute(select(Seller))).scalars().first()
        session.add(
            SellerBot(
                seller_id=seller.id,
                bot_token_encrypted=b"x",
                bot_username="second_shop",
                telegram_bot_id=4242,
            )
        )
        await session.commit()

    async with db() as session:
        f = await platform_stats.funnel(session)
        t = await platform_stats.totals(session)
    assert t.shops == 2
    assert f.with_shop == 1 and f.with_bot == 1


@pytest.mark.asyncio
async def test_payout_step_counts_only_sent(db):
    await make_order(db, invoice_id=555001, total=Decimal("100"))
    await _pay(db, 555001)
    async with db() as session:
        seller = (await session.execute(select(Seller))).scalars().first()
        bot = (await session.execute(select(SellerBot))).scalars().first()
        session.add(
            PayoutBatch(seller_id=seller.id, bot_id=bot.id, amount=Decimal("95"), status="pending")
        )
        await session.commit()

    async with db() as session:
        assert (await platform_stats.funnel(session)).with_payout == 0

    async with db() as session:
        batch = (await session.execute(select(PayoutBatch))).scalars().first()
        batch.status = "sent"
        await session.commit()

    async with db() as session:
        assert (await platform_stats.funnel(session)).with_payout == 1


@pytest.mark.asyncio
async def test_top_shops_sorted_by_turnover_with_readable_name(db):
    await make_order(db, invoice_id=555001, total=Decimal("30"))
    await _pay(db, 555001)

    async with db() as session:
        bot = (await session.execute(select(SellerBot))).scalars().first()
        bot.shop_name = "Кофейня у дома"
        await session.commit()

    async with db() as session:
        top = await platform_stats.top_shops(session)

    assert len(top) == 1
    # имя то же, что видит покупатель в шапке витрины, а не «магазин #7»
    assert top[0].name == "Кофейня у дома"
    assert top[0].gmv == Decimal(30) and top[0].orders == 1


@pytest.mark.asyncio
async def test_top_shops_falls_back_to_username(db):
    await make_order(db, invoice_id=555001, total=Decimal("30"))
    await _pay(db, 555001)
    async with db() as session:
        top = await platform_stats.top_shops(session)
    assert top[0].name == "@shop_bot"


@pytest.mark.asyncio
async def test_old_sales_drop_out_of_the_weekly_window(db):
    """Оборот за 7 дней не должен включать прошлогоднюю продажу."""
    from datetime import datetime, timedelta, timezone

    await make_order(db, invoice_id=555001, total=Decimal("100"))
    await _pay(db, 555001)
    async with db() as session:
        order = (await session.execute(select(Order))).scalars().first()
        order.paid_at = datetime.now(timezone.utc) - timedelta(days=60)
        await session.commit()

    async with db() as session:
        s = await platform_stats.sales(session)
    assert s.gmv == Decimal(100)  # за всё время осталась
    assert s.gmv_30d == 0 and s.gmv_7d == 0
