"""Relay-чат по заказу: продавец пишет из кабинета, покупатель — в диалоге
с ботом магазина; все сообщения идут через бэкенд, личности друг другу
стороны не видят (наружу только sender='seller'|'customer').

Чат жёстко привязан к одному заказу (order_id unique): смешать переписку
разных заказов на уровне схемы невозможно. Окно активности — 72 часа после
доставки заказа, дальше чат читается, но не пишется (см. app/services/chat.py).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.models.catalog import new_image_token


class OrderChat(Base, CreatedAtMixin):
    __tablename__ = "order_chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, index=True
    )
    # Изоляция по магазину — как у всех ресурсов: bot_id, а не seller_id
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="RESTRICT"), index=True
    )
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="RESTRICT"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)

    # active | locked_by_timeout | archived; задел под будущие исключения
    # (dispute_opened и т.п.) — новые значения добавляются без миграций
    status: Mapped[str] = mapped_column(String(24), default="active", server_default="active")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages = relationship(
        "ChatMessage", back_populates="chat", cascade="all, delete-orphan"
    )


class ChatMessage(Base, CreatedAtMixin):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("order_chats.id", ondelete="CASCADE"), index=True
    )
    # seller | customer — роли сторон, никаких внешних идентификаторов
    sender: Mapped[str] = mapped_column(String(8))
    body: Mapped[str] = mapped_column(Text)

    # message_id в Telegram-диалоге покупателя (для сообщений продавца):
    # ответ-реплай на него адресует сообщение именно этому заказу
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)

    # фото-сообщение: токен строки в chat_images; без фото — None, тогда body
    # обязателен. Фото без подписи хранится с пустым body (""), колонка NOT NULL
    image_token: Mapped[str | None] = mapped_column(String(64))

    chat = relationship("OrderChat", back_populates="messages")

    @property
    def image_url(self) -> str | None:
        """Адрес картинки для API/фронта; None — текстовое сообщение."""
        return f"/api/chat-images/{self.image_token}" if self.image_token else None


class ChatMessageArchive(Base):
    """Холодное хранилище переписки: сюда джоб переносит сообщения чатов,
    заблокированных больше archive_chat_after_days назад (см.
    app/services/chat.py). Колонки повторяют ChatMessage + archived_at;
    чтение истории объединяет обе таблицы."""

    __tablename__ = "chat_messages_archive"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("order_chats.id", ondelete="CASCADE"), index=True
    )
    sender: Mapped[str] = mapped_column(String(8))
    body: Mapped[str] = mapped_column(Text)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    image_token: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # default (а не только server_default): значение уходит прямо в INSERT.
    # Тесты поднимают схему через create_all и серверный дефолт получают, а на
    # мигрированной базе его не было — вставка падала бы NOT NULL только в проде.
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    @property
    def image_url(self) -> str | None:
        return f"/api/chat-images/{self.image_token}" if self.image_token else None


class ChatImage(Base, CreatedAtMixin):
    """Фото переписки лежит в БД так же, как фото товаров (см. ProductImage):
    байты не больше MAX_IMAGE_BYTES, тип — только из белого списка, адрес —
    случайный токен вместо порядкового id."""

    __tablename__ = "chat_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=new_image_token
    )
    # фото принадлежит магазину и чату конкретного заказа; чат удаляется
    # только вместе с заказом, картинки живут столько же
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("order_chats.id", ondelete="CASCADE"), index=True
    )
    mime: Mapped[str] = mapped_column(String(32))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
