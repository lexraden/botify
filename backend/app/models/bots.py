from sqlalchemy import BigInteger, Boolean, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin


class SellerBot(Base, CreatedAtMixin):
    """Бот продавца, созданный им через @BotFather и подключённый к платформе.
    Токен хранится только в зашифрованном виде (Fernet, ключ в env);
    во внешних путях (вебхуки) фигурирует только суррогатный id."""

    __tablename__ = "seller_bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)

    # Название магазина: из него собирается имя и юзернейм для создаваемого
    # бота, оно же — шапка витрины. У магазинов, заведённых до этого поля,
    # совпадает с юзернеймом бота.
    title: Mapped[str | None] = mapped_column(String(128))

    # Пусто, пока бот не подключён: онбординг начинается с названия магазина,
    # а бот появляется последним шагом. Черновик — это строка с пустым токеном,
    # отдельного флага нет намеренно (был бы второй источник правды).
    bot_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    bot_username: Mapped[str | None] = mapped_column(String(64))
    telegram_bot_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)  # из getMe

    @property
    def is_draft(self) -> bool:
        """Магазин заведён, но бота к нему ещё не подключили."""
        return self.bot_token_encrypted is None

    @property
    def display_name(self) -> str:
        return self.title or (f"@{self.bot_username}" if self.bot_username else "Магазин")

    webhook_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | active | failed
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Настройки из /settings самого бота: приветствие покупателю на /start
    # и кнопка открытия витрины (None -> стандартный «🛍 Открыть каталог»)
    welcome_text: Mapped[str | None] = mapped_column(Text)
    show_catalog_button: Mapped[bool] = mapped_column(Boolean, default=True)
    catalog_button_text: Mapped[str | None] = mapped_column(String(64))

    seller = relationship("Seller", back_populates="bots")
    customers = relationship("Customer", back_populates="bot", cascade="all, delete-orphan")

