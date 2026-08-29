import secrets
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.catalog import JsonB


def new_spend_token() -> str:
    """Случайный spend_id для пачки выплат (см. PayoutBatch.spend_id)."""
    return secrets.token_urlsafe(16)


# Заказ считается состоявшимся с момента оплаты; дальше меняется только
# стадия доставки, поэтому во всех денежных выборках статусы одни и те же
PAID_STATUSES = ("paid", "fulfilled", "delivered")


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
    # Когда неоплаченный заказ перестаёт ждать оплату (app/services/order_health.py).
    # Живёт столько же, сколько счёт в Crypto Pay: выписали новый счёт — счётчик
    # пошёл заново. NULL у старых заказов и после оплаты — они не истекают.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Момент доставки (delivered). От него считается окно чата заказа —
    # 72 часа на обсуждение (app/services/chat.py)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Когда продавцу ушло напоминание, что заказ оплачен, но не отправлен
    # (app/services/order_health.py). NULL — ещё не напоминали.
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fulfillment: Mapped[dict | None] = mapped_column(JsonB)  # трек-номер / ссылка / файл

    # Куда везти: {name, phone, address}. Только у заказов с физическими
    # позициями; у цифровых остаётся None. Единственные данные покупателя,
    # которые видит продавец, — без них он физически не может отправить товар.
    delivery: Mapped[dict | None] = mapped_column(JsonB)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payout = relationship("Payout", back_populates="order", uselist=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    # Какая именно вариация куплена. NULL — товар без вариаций (так выглядят
    # все заказы до появления таблицы product_variants)
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT")
    )
    # Снимок свойств вариации на момент покупки — «Красный · M». Цену мы уже
    # снимаем по той же причине: продавец переименует вариацию или заменит
    # набор размеров, а в старом заказе должно остаться то, что купили
    variant_label: Mapped[str | None] = mapped_column(String(128))
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
    # Выплаты копятся по магазину, а не по продавцу целиком: один бот —
    # один магазин со своими деньгами (docs/project-brief.md, п. 8.3)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="RESTRICT"), index=True
    )

    amount: Mapped[float] = mapped_column(Numeric(18, 6))
    # pending | sent | failed | too_small (минимум оказался выше нашего — копим дальше)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # Случайный токен, уходящий в Crypto Pay как spend_id. Не производная от id:
    # сброс базы начинает нумерацию заново, и batch-{id} столкнулся бы с уже
    # использованным spend_id (SPEND_ID_ALREADY_USED). Генерируется один раз
    # при создании пачки и не меняется при повторных попытках отправить её.
    spend_id: Mapped[str] = mapped_column(String(64), unique=True, default=new_spend_token)
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
    # Магазин, в котором прошла продажа — по нему копится и выводится выплата
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="RESTRICT"), index=True
    )

    amount: Mapped[float] = mapped_column(Numeric(18, 6))
    commission: Mapped[float] = mapped_column(Numeric(18, 6))  # наша комиссия
    # Комиссия Crypto Pay за приём платежа. Платит её платформа из своей
    # комиссии, доля продавца от неё не зависит — храним ради учёта маржи
    provider_fee: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
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
