from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class ProductReview(Base, CreatedAtMixin):
    """Отзыв о товаре. Оставить можно только на позицию из своего заказа в
    статусе delivered — накрутка исключена архитектурно (пара
    order_id + product_id уникальна, повторная отправка правит оценку).

    Личность автора не раскрывается нигде: наружу идёт случайный псевдоним
    (author_name), сгенерированный при создании и никак не связанный
    с покупателем.

    Наследуемые отзывы (source='inherited') — при копии магазина переносятся
    без заказа и покупателя: order_id=NULL, customer_id=NULL, source='inherited'.
    Рейтинг витрины считает их так же, как обычные.
    """

    __tablename__ = "product_reviews"
    __table_args__ = (
        # Частичная уникальность через индекс в миграции:
        # (order_id, product_id) уникально ТОЛЬКО для order_id IS NOT NULL.
        # Для наследуемых (order_id=NULL) дубли допускаются.
        # Старый констрейнт оставлен для совместимости, но логику перекрывает
        # частичный индекс uq_review_once_per_order_item_partial.
        UniqueConstraint("order_id", "product_id", name="uq_review_once_per_order_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    body: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)

    # Модерация: отзывы с высокой оценкой (>= review_auto_publish_min) видны
    # сразу, низкие ждут одобрения продавца; через review_moderation_days
    # ожидающие публикуются сами. Правка оценки пересчитывает статус по тому
    # же порогу, правка отклонённого возвращает его в ожидание.
    status: Mapped[str] = mapped_column(String(16), default="published")
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # один ответ продавца на отзыв (не поток); повторная отправка правит его
    reply_body: Mapped[str | None] = mapped_column(Text)
    reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))