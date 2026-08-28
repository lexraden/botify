"""Администратор магазина: продавец, которому владелец выдал доступ.

Владелец приглашает по @username или Telegram ID (кандидат должен быть
известен платформе — нажать /start у hub-бота). Админ ведёт магазин
наравне с владельцем, кроме денег: вывод и удаление магазина остаются
у владельца.

Роль сейчас одна — «admin»; поле оставлено, чтобы будущие роли
(контент-менеджер, поддержка) не потребовали новой таблицы.
"""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class StoreAdmin(Base, CreatedAtMixin):
    __tablename__ = "store_admins"
    __table_args__ = (
        UniqueConstraint("bot_id", "seller_id", name="uq_store_admins_bot_seller"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="admin")
