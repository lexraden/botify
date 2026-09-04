from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class ShopEvent(Base, CreatedAtMixin):
    """Сырые события витрины для статистики магазина.

    Хранятся построчно, а не счётчиками: так можно считать любые срезы
    (за период, по товару, уникальные покупатели) без миграций.
    """

    __tablename__ = "shop_events"
    __table_args__ = (Index("ix_shop_events_bot_type", "bot_id", "type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL")
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))

    type: Mapped[str] = mapped_column(String(32))  # shop_open | product_view | checkout_start
