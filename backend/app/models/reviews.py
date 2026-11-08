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

    Наследуемые отзывы (source='inherited') переносятся копией магазина
    (services/shop_copy.py): без заказа и покупателя (order_id/customer_id
    NULL), поэтому на «свой заказ» они не тянут ни в одном запросе —
    все выборки по заказу/покупателю фильтруют customer_id IS NOT NULL.
    Рейтинг витрины считает их наравне с обычными: среднее — по всем
    опубликованным отзывам бота.
    """

    __tablename__ = "product_reviews"
    __table_args__ = (
        # Дубли NULL-ами не считаются (и в Postgres, и в SQLite), поэтому
        # наследуемые отзывы (order_id IS NOT NULL не выполняется) могут
        # повторяться по (NULL, product_id), а для настоящих заказов
        # уникальность пары работает как раньше. Частичный индекс в
        # миграции d4e5f6a7b8c9 закрепляет то же явным образом.
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
    # подтверждённой покупки. NULL — только у наследуемых (см. докстринг)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    # NULL — только у наследуемых: свой отзыв всегда знает своего покупателя
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)  # 1..5, диапазон валидируется в API
    body: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(64))
    # normal — оставлен покупателем за доставленный заказ;
    # inherited — перенесён копией магазина со старого бота
    source: Mapped[str] = mapped_column(String(16), default="normal")

    # Модерация: отзывы с высокой оценкой (>= review_auto_publish_min) видны
    # сразу, низкие ждут одобрения продавца; через review_moderation_days
    # ожидающие публикуются сами. Правка оценки пересчитывает статус по тому
    # же порогу, правка отклонённого возвращает его в ожидание.
    status: Mapped[str] = mapped_column(String(16), default="published")
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # один ответ продавца на отзыв (не поток); повторная отправка правит его
    reply_body: Mapped[str | None] = mapped_column(Text)
    reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
