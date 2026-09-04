from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin


class Customer(Base, CreatedAtMixin):
    """Покупатель = юзер конкретного seller-бота. Изоляция баз: продавец видит
    только своих покупателей (все выборки фильтруются по seller_id)."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("telegram_id", "bot_id", name="uq_customer_per_bot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True)

    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(8))
    # Ручной выбор языка в профиле Mini App; None = человек не выбирал — тогда
    # язык уведомлений берётся из language_code (ru* -> RU, остальные -> EN).
    locale: Mapped[str | None] = mapped_column(String(8))
    source: Mapped[str | None] = mapped_column(String(128))  # UTM / deep-link параметр из /start
    # Настоящий бан: закрывает доступ к Mini App целиком.
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    # Бот заблокирован покупателем или чат удалён — сообщения ему не доходят.
    # Влияет только на рассылки: глушить бота не значит отказываться от своих
    # заказов, истории и переписки с продавцом.
    mailing_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    bot = relationship("SellerBot", back_populates="customers")
