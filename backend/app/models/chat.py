"""Relay-чат по заказу: продавец пишет из кабинета, покупатель — в диалоге
с ботом магазина; все сообщения идут через бэкенд, личности друг другу
стороны не видят (наружу только sender='seller'|'customer').

Чат жёстко привязан к одному заказу (order_id unique): смешать переписку
разных заказов на уровне схемы невозможно. Окно активности — 72 часа после
доставки заказа, дальше чат читается, но не пишется (см. app/services/chat.py).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin


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

    chat = relationship("OrderChat", back_populates="messages")


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
