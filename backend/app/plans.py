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


# Платные тарифы по возрастанию: старший включает всё, что даёт младший
PAID_PLANS = ("pro", "plus")


@dataclass(frozen=True)
class PlanLimits:
    max_products: int | None  # None = без ограничения
    max_services: int | None
    max_mailing_recipients: int | None
    # Приём оплаты по реквизитам продавца прямо в чате заказа (p2p).
    # Не лимит, а функция тарифа — но живёт здесь же, чтобы «что даёт тариф»
    # читалось в одном месте, а не в трёх проверках по коду.
    p2p_payments: bool = False


FREE = PlanLimits(max_products=10, max_services=10, max_mailing_recipients=1000)
PRO = PlanLimits(max_products=None, max_services=None, max_mailing_recipients=None)
PLUS = PlanLimits(
    max_products=None, max_services=None, max_mailing_recipients=None, p2p_payments=True
)

LIMITS_BY_PLAN = {"free": FREE, "pro": PRO, "plus": PLUS}


def active_plan(seller: Seller) -> str:
    """Тариф, действующий прямо сейчас: «free», если платный истёк.

    Одно место, где срок превращается в тариф, — иначе проверка «оплачено ли»
    расползается по коду и где-нибудь окажется забытой.
    """
    if seller.plan not in PAID_PLANS:
        return "free"
    if seller.pro_expires_at is None:
        return seller.plan  # бессрочный (выдан вручную)
    from datetime import datetime, timezone

    expires = seller.pro_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return seller.plan if expires > datetime.now(timezone.utc) else "free"


def limits_for(seller: Seller) -> PlanLimits:
    return LIMITS_BY_PLAN[active_plan(seller)]


def is_pro(seller: Seller) -> bool:
    """Есть ли у продавца действующий платный тариф — любой из них."""
    return active_plan(seller) in PAID_PLANS


def over_limit(used: int, cap: int | None) -> bool:
    return cap is not None and used >= cap
