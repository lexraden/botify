from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class Channel(Base, CreatedAtMixin):
    """Канал/группа продавца, куда его seller-бот добавлен админом.
    Используется для авто-приёма заявок на вступление (лид-магнит из брифа)."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True)

    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(256))

    auto_accept: Mapped[bool] = mapped_column(Boolean, default=True)
    greeting_text: Mapped[str | None] = mapped_column(Text)  # приветствие вступившему в ЛС
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
