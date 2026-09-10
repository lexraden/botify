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

    # shop_open — вход в витрину; product_view — открытая карточка товара
    # (именно открытая: прокрутка мимо карточки в сетке событием не считается);
    # checkout_start — открытое оформление заказа
    type: Mapped[str] = mapped_column(String(32))
