"""Платежи за Pro-подписку продавца.

Строка на каждую успешную оплату, а не «текущее состояние подписки»: сама
подписка живёт двумя полями продавца (`Seller.plan`, `Seller.pro_expires_at`),
а эта таблица нужна для трёх вещей — идемпотентности вебхука, учёта выручки
платформы и ответа на вопрос «за что списали».

Идемпотентность держится уникальностью внешнего идентификатора платежа:
Crypto Pay ретраит вебхук, а Telegram может доставить successful_payment
повторно. Вторая вставка с тем же invoice_id / charge_id падает на уникальном
индексе, и подписка не продлевается дважды за одни деньги.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class SubscriptionPayment(Base, CreatedAtMixin):
    __tablename__ = "subscription_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("sellers.id", ondelete="RESTRICT"), index=True
    )

    # crypto | stars — чем заплатили. Суммы держим обе и заполняем ту, что
    # реально списана: сравнивать выручку в разных валютах всё равно придётся.
    method: Mapped[str] = mapped_column(String(16))
    amount_usdt: Mapped[float | None] = mapped_column(Numeric(18, 6))
    amount_stars: Mapped[int | None] = mapped_column(Integer)

    # На сколько дней продлили — цена и период могут меняться, а в старом
    # платеже должно остаться то, что продали
    period_days: Mapped[int] = mapped_column(Integer)

    # Внешние идентификаторы платежа; заполнен ровно один, по способу оплаты
    invoice_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    telegram_charge_id: Mapped[str | None] = mapped_column(String(128), unique=True)

    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Докуда продлилась подписка этим платежом — чтобы не пересчитывать заново
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
