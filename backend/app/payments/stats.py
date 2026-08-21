"""Деньги платформы: сколько заработано комиссий и сколько из них съел сервис.

Наша комиссия достаётся нам не целиком — из неё платится комиссия Crypto Pay
за приём платежа (см. app/payments/service.py). Чистая маржа = одно минус
другое, и увидеть её больше негде: в выплатах продавцу этих чисел нет.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Order, Payout
from app.models.orders import PAID_STATUSES

# Crypto Pay снижает ставку по обороту оплаченных инвойсов за 30 дней.
# Порог в USD -> ставка; список от большего порога к меньшему.
FEE_TIERS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal(100_000), Decimal("2.5")),
    (Decimal(75_000), Decimal("2.6")),
    (Decimal(50_000), Decimal("2.7")),
    (Decimal(25_000), Decimal("2.8")),
    (Decimal(10_000), Decimal("2.9")),
)


@dataclass(frozen=True)
class PlatformMargin:
    commission: Decimal       # начислено нашей комиссии за всё время
    provider_fee: Decimal     # из неё уплачено Crypto Pay
    volume_30d: Decimal       # оборот оплаченных заказов за 30 дней
    next_tier: tuple[Decimal, Decimal] | None  # (сколько добрать, будущая ставка)

    @property
    def net(self) -> Decimal:
        return self.commission - self.provider_fee


def _next_tier(volume: Decimal) -> tuple[Decimal, Decimal] | None:
    """Ближайший порог скидки: сколько оборота не хватает и какая там ставка."""
    for threshold, rate in reversed(FEE_TIERS):  # от ближайшего порога к дальнему
        if volume < threshold:
            return threshold - volume, rate
    return None  # оборот выше максимального порога — ставка уже минимальная


async def platform_margin(session) -> PlatformMargin:
    commission, provider_fee = (
        await session.execute(
            select(
                func.coalesce(func.sum(Payout.commission), 0),
                func.coalesce(func.sum(Payout.provider_fee), 0),
            )
        )
    ).one()
    volume_30d = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status.in_(PAID_STATUSES),
                Order.paid_at >= datetime.now(timezone.utc) - timedelta(days=30),
            )
        )
    ).scalar_one()
    return PlatformMargin(
        commission=Decimal(commission),
        provider_fee=Decimal(provider_fee),
        volume_30d=Decimal(volume_30d),
        next_tier=_next_tier(Decimal(volume_30d)),
    )
