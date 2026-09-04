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
    """

    __tablename__ = "product_reviews"
    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_review_once_per_order_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT — как у OrderItem.product_id: товар с заказами удаляется только
    # деактивацией, так что живой отзыв всегда указывает на существующий товар
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    # отзыв умирает вместе со своим заказом: без него это была бы оценка без
    # подтверждённой покупки
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)  # 1..5, диапазон валидируется в API
    body: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(64))

    # Модерация: отзывы с высокой оценкой (>= review_auto_publish_min) видны
    # сразу, низкие ждут одобрения продавца; через review_moderation_days
    # ожидающие публикуются сами. Правка оценки пересчитывает статус по тому
    # же порогу, правка отклонённого возвращает его в ожидание.
    status: Mapped[str] = mapped_column(String(16), default="published")
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # один ответ продавца на отзыв (не поток); повторная отправка правит его
    reply_body: Mapped[str | None] = mapped_column(Text)
    reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
