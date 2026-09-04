"""Pro-подписка продавца: счёт, зачисление, продление.

Два способа оплаты — Crypto Pay (USDT) и Telegram Stars — приводят к одному
и тому же: строка в subscription_payments и сдвинутый `pro_expires_at`.
Разное у них только то, как деньги приходят.

Почему звёзды здесь проще, чем в заказах: подписку продавец платит самой
платформе, а кабинет он открывает из hub-бота. Значит счёт выставляет тот же
бот, в котором открыт Mini App, и звёзды падают на баланс платформы. Ни
кросс-ботового инвойса, ни выплат чужих денег, ни кассового разрыва — всё
то, из-за чего звёзды в заказах отложены (docs/stars-payments.md), здесь
не возникает.

Идемпотентность держится уникальностью внешнего идентификатора платежа
(invoice_id / telegram_charge_id), а не проверкой «уже про или нет»: продлить
подписку заранее — законная операция, а принять одни деньги дважды — нет.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import get_session
from app.models import Seller, SubscriptionPayment
from app.plans import PAID_PLANS, active_plan

logger = logging.getLogger(__name__)

# Префикс payload у счёта: по нему вебхук отличает подписку от заказа
# (у заказов payload вида «order:{id}»). Тариф пишем туда же — иначе к моменту
# зачисления неизвестно, за что заплатили, а цены у тарифов разные.
PAYLOAD_PREFIX = "sub:"


def payload_for(seller_id: int, plan: str) -> str:
    return f"{PAYLOAD_PREFIX}{seller_id}:{plan}"


def parse_payload(payload: str | None) -> tuple[int, str] | None:
    """(seller_id, тариф) из payload счёта; None — это не подписочный счёт."""
    if not payload or not payload.startswith(PAYLOAD_PREFIX):
        return None
    parts = payload[len(PAYLOAD_PREFIX):].split(":")
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in PAID_PLANS:
        return None
    return int(parts[0]), parts[1]


def price_of(plan: str) -> tuple[float, int]:
    """(цена в USDT, цена в звёздах) тарифа."""
    settings = get_settings()
    if plan == "plus":
        return settings.plus_price_usdt, settings.plus_price_stars
    return settings.pro_price_usdt, settings.pro_price_stars


def _extended_to(seller: Seller, days: int, now: datetime) -> datetime:
    """Докуда продлится подписка.

    Отсчитываем от текущего окончания, если оно ещё не прошло: продавец,
    оплативший заранее, не должен терять остаток оплаченного месяца.
    """
    current = seller.pro_expires_at
    if current is not None and current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    base = current if current is not None and current > now else now
    return base + timedelta(days=days)


async def grant_plan(
    seller_id: int,
    plan: str,
    *,
    method: str,
    invoice_id: int | None = None,
    telegram_charge_id: str | None = None,
    amount_usdt: Decimal | None = None,
    amount_stars: int | None = None,
) -> bool:
    """Зачислить оплату и продлить Pro. False — этот платёж уже зачтён.

    Повторная доставка вебхука падает на уникальном индексе внешнего
    идентификатора: подписка не продлевается дважды за одни деньги.
    """
    settings = get_settings()
    days = settings.pro_period_days
    now = datetime.now(timezone.utc)

    async with get_session() as session:
        seller = await session.get(Seller, seller_id)
        if seller is None:
            logger.error("Оплата подписки для несуществующего продавца %s", seller_id)
            return False

        # Продлеваем от текущего окончания только в пределах того же тарифа:
        # переход с Pro на Plus — это другой продукт, и «доплатить остаток
        # старого» мы не умеем; отсчёт начинается заново.
        same_plan = active_plan(seller) == plan
        expires_at = _extended_to(seller, days, now) if same_plan else now + timedelta(days=days)
        session.add(
            SubscriptionPayment(
                seller_id=seller_id,
                method=method,
                amount_usdt=amount_usdt,
                amount_stars=amount_stars,
                period_days=days,
                invoice_id=invoice_id,
                telegram_charge_id=telegram_charge_id,
                paid_at=now,
                expires_at=expires_at,
            )
        )
        seller.plan = plan
        seller.pro_expires_at = expires_at
        try:
            await session.commit()
        except IntegrityError:
            # тот же платёж пришёл повторно — подписку не трогаем
            await session.rollback()
            logger.info("Повторная доставка оплаты подписки продавца %s — пропущена", seller_id)
            return False

    logger.info("Тариф %s продавцу %s до %s (%s)", plan, seller_id, expires_at, method)
    return True


async def create_crypto_invoice(seller_id: int, plan: str) -> str | None:
    """Счёт Crypto Pay на подписку. None — Crypto Pay не настроен."""
    from app.payments.client import get_crypto_pay

    crypto = get_crypto_pay()
    if crypto is None:
        return None
    settings = get_settings()
    usdt, _ = price_of(plan)
    invoice = await crypto.create_invoice(
        asset="USDT",
        amount=float(usdt),
        description=f"Botify {plan.capitalize()} — {settings.pro_period_days} дней",
        payload=payload_for(seller_id, plan),
        allow_comments=False,
        allow_anonymous=False,
        expires_in=3600,
    )
    return invoice.bot_invoice_url


async def create_stars_link(seller_id: int, plan: str) -> str:
    """Ссылка на оплату звёздами. Счёт выставляет hub-бот — тот же, в котором
    у продавца открыт кабинет, поэтому звёзды приходят платформе."""
    from aiogram.types import LabeledPrice

    from app.bots.hub import hub_bot

    settings = get_settings()
    _, stars = price_of(plan)
    title = f"Botify {plan.capitalize()}"
    return await hub_bot.create_invoice_link(
        title=title,
        description=f"Безлимитный каталог и рассылки, {settings.pro_period_days} дней",
        payload=payload_for(seller_id, plan),
        currency="XTR",  # звёзды
        prices=[LabeledPrice(label=title, amount=stars)],
    )


async def remind_expiring() -> int:
    """Напомнить продавцам, у кого подписка кончается через pro_reminder_days.

    Напоминание одно на срок: метка — `Seller.pro_reminded_for`, куда пишется
    то самое окончание, о котором уже сказали. Без метки джоб слал бы письмо
    каждые десять минут все три дня подряд.
    """
    from sqlalchemy import select

    from app.bots.hub import hub_bot
    from app.services import seller_texts

    settings = get_settings()
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=settings.pro_reminder_days)

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Seller).where(
                    Seller.plan.in_(PAID_PLANS),
                    Seller.pro_expires_at.is_not(None),
                    Seller.pro_expires_at > now,
                    Seller.pro_expires_at <= deadline,
                )
            )
        ).scalars().all()
        targets = [s for s in rows if s.pro_reminded_for != s.pro_expires_at]
        for seller in targets:
            seller.pro_reminded_for = seller.pro_expires_at
        payload = [
            (
                s.telegram_id,
                seller_texts.text(
                    seller_texts.seller_locale(s),
                    "pro.expiring",
                    plan=s.plan.capitalize(),
                    days=settings.pro_reminder_days,
                ),
            )
            for s in targets
        ]
        # метку ставим до отправки: не доставленное напоминание — мелочь,
        # а повторная рассылка каждые десять минут — нет
        await session.commit()

    sent = 0
    for chat_id, text in payload:
        try:
            await hub_bot.send_message(chat_id, text)
            sent += 1
        except Exception:
            logger.warning("Не удалось напомнить о подписке %s", chat_id, exc_info=True)
    return sent
