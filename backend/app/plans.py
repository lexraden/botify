"""Тарифы продавцов.

Сейчас лимиты НЕ применяются (enforce_plan_limits=False) — считается только
использование, чтобы кабинет мог показывать «8 из 10». Когда Pro будет
запущен, флаг включается, и лимиты начинают работать:

  • превышение НИКОГДА ничего не удаляет — ни товары, ни базу покупателей.
    Продавцу просто нельзя добавить новый товар или запустить рассылку по
    базе больше лимита. Всё, что уже накоплено, остаётся на месте;
  • продавцы, у которых на момент запуска Pro уже больше лимита, продолжают
    работать со своим каталогом и базой — блокируется только рост.
"""

from dataclasses import dataclass

from app.models import Seller

# Услугами считаем digital и service: у них общий смысл «нематериальное»
SERVICE_TYPES = ("digital", "service")


@dataclass(frozen=True)
class PlanLimits:
    max_products: int | None  # None = без ограничения
    max_services: int | None
    max_mailing_recipients: int | None


FREE = PlanLimits(max_products=10, max_services=10, max_mailing_recipients=1000)
PRO = PlanLimits(max_products=None, max_services=None, max_mailing_recipients=None)


def limits_for(seller: Seller) -> PlanLimits:
    return PRO if is_pro(seller) else FREE


def is_pro(seller: Seller) -> bool:
    """Pro активен, пока не истёк срок (pro_expires_at=None у бессрочного)."""
    if seller.plan != "pro":
        return False
    if seller.pro_expires_at is None:
        return True
    from datetime import datetime, timezone

    return seller.pro_expires_at > datetime.now(timezone.utc)


def over_limit(used: int, cap: int | None) -> bool:
    return cap is not None and used >= cap
