from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.catalog import JsonB


class Order(Base, CreatedAtMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="RESTRICT"), index=True)
    # Магазин (бот), в котором оформлен заказ — статистика и выдача заказов
    # фильтруются по нему, а не по продавцу целиком
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="RESTRICT"), index=True
    )
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)

    # pending_payment -> paid -> fulfilled (продавец приложил трек/ссылку/файл)
    # -> delivered (переслано покупателю); cancelled — не оплачен/истёк
    status: Mapped[str] = mapped_column(String(24), default="pending_payment", index=True)

    total: Mapped[float] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(8), default="USDT")
    comment: Mapped[str | None] = mapped_column(Text)  # «Add Comment...» с экрана checkout

    invoice_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)  # Crypto Pay invoice
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fulfillment: Mapped[dict | None] = mapped_column(JsonB)  # трек-номер / ссылка / файл

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payout = relationship("Payout", back_populates="order", uselist=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Numeric(18, 6))  # цена на момент покупки

    order = relationship("Order", back_populates="items")


class PayoutBatch(Base, CreatedAtMixin):
    """Один transfer в Crypto Pay, покрывающий несколько выплат сразу.

    У Crypto Pay есть минимальная сумма перевода, и одна продажа на пару
    долларов её не набирает. Поэтому доли продавца копятся в payouts, а в
    пачку попадают только когда сумма уже проходит минимум — так перевод
    не отбивается с AMOUNT_TOO_SMALL.
    """

    __tablename__ = "payout_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="RESTRICT"), index=True)

    amount: Mapped[float] = mapped_column(Numeric(18, 6))
    # pending | sent | failed | too_small (минимум оказался выше нашего — копим дальше)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    last_error: Mapped[str | None] = mapped_column(String(512))
    transfer_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    payouts = relationship("Payout", back_populates="batch")


class Payout(Base, CreatedAtMixin):
    """Доля продавца по одному заказу. Уходит не сама по себе, а в составе
    PayoutBatch — см. app/payments/payouts.py."""

    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), unique=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="RESTRICT"), index=True)

    amount: Mapped[float] = mapped_column(Numeric(18, 6))
    commission: Mapped[float] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | sent | failed
    # Причина последнего отказа от Crypto Pay — чтобы не искать её в логах
    last_error: Mapped[str | None] = mapped_column(String(512))
    # transfer_id общий для всей пачки, поэтому без unique
    transfer_id: Mapped[int | None] = mapped_column(BigInteger)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("payout_batches.id", ondelete="SET NULL"), index=True
    )

    order = relationship("Order", back_populates="payout")
    batch = relationship("PayoutBatch", back_populates="payouts")
