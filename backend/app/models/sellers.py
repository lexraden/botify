from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin


class Seller(Base, CreatedAtMixin):
    """Продавец = юзер hub-бота. Покупатели живут в отдельной таблице customers
    и не пересекаются с продавцами по построению."""

    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(8))

    # Онбординг идёт в Mini App; прогресс хранится здесь, чтобы пересоздание
    # webview (уход в @BotFather/@CryptoBot и обратно) не сбрасывало шаг:
    # payment_pending -> payment_done -> bot_pending -> bot_done
    onboarding_step: Mapped[str] = mapped_column(String(32), default="payment_pending")
    # Принятие условий использования на первом экране онбординга; null = ещё не принял
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Продавец нажал /start у @CryptoBot — без этого transfer не сработает
    cryptobot_connected: Mapped[bool] = mapped_column(Boolean, default=False)

    commission_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=5)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)

    # Монетизация MVP — только комиссия. Поля ниже — задел под месячную Pro-подписку:
    # план становится платным, когда база покупателей продавца превышает 1000
    # (см. docs/AUDIT.md, решение владельца от 2026-08-18).
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free | pro
    pro_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    bots = relationship("SellerBot", back_populates="seller", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="seller", cascade="all, delete-orphan")
