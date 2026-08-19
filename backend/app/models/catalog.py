from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin

JsonB = JSON().with_variant(JSONB(), "postgresql")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)
    # Каждый бот — отдельный магазин: каталог не шарится между ботами продавца
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Product(Base, CreatedAtMixin):
    """Товары и услуги в одной таблице; различаются полем type.
    Для digital/service контент выдачи (ссылка/файл/инвайт/главы) лежит в digital_content."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)
    # Магазин, которому принадлежит товар (см. Category.bot_id)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))

    type: Mapped[str] = mapped_column(String(16))  # physical | digital | service
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(512))

    # MVP: единая валюта каталога — USDT (решение владельца от 2026-08-18)
    price: Mapped[float] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(8), default="USDT")

    digital_content: Mapped[dict | None] = mapped_column(JsonB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    seller = relationship("Seller", back_populates="products")
