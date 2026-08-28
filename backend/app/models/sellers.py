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
    # Ручной выбор языка hub-бота (/lang). None = не выбирал: тогда ru* по
    # language_code идёт RU, остальным EN, а при неизвестном языке Telegram —
    # RU (у покупателей наоборот: неизвестный — EN, платформа для них англ.
    # по умолчанию; у продавцов hub всегда был русским, и молча переводить
    # существующих на EN нельзя). Разбор правила — services/seller_texts.py.
    locale: Mapped[str | None] = mapped_column(String(8))

    # Онбординг идёт в Mini App; прогресс хранится здесь, чтобы пересоздание
    # webview (уход в @BotFather и обратно) не сбрасывало шаг.
    # Единственный шаг — подключение бота. Дефолт ниже — питоновский (все
    # вставки идут через ORM); серверный DEFAULT в базе остался старым
    # ('payment_pending') как legacy и роли не играет.
    onboarding_step: Mapped[str] = mapped_column(String(32), default="bot_pending")
    # Принятие условий использования на первом экране онбординга; null = ещё не принял
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Ставится по факту состоявшейся выплаты: API Crypto Pay не умеет отвечать,
    # открыт ли @CryptoBot, а спрашивать об этом продавца бессмысленно. Ничего
    # не блокирует — справочный флаг «выплаты до него уже доходили».
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
