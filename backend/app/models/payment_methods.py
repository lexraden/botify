"""Реквизиты магазина для оплаты переводом (p2p) — функция тарифа Pro.

Деньги по такому заказу идут мимо платформы: покупатель переводит их прямо
продавцу, а платформа только показывает реквизиты и ведёт переписку. Отсюда
два следствия, важных для всего остального кода:

- выплаты (`Payout`) по p2p-заказу не создаются: платформе нечего выплачивать;
- подтвердить оплату может только продавец — он единственный, кто видит свой
  счёт. Ни вебхука, ни сверки здесь нет и быть не может.

Способов у магазина несколько (карта, СБП, крипто-адрес), покупатель выбирает
на чекауте. Номер и имя получателя шифруются Fernet тем же ключом, что и
токены ботов: в дампе базы платёжные данные людей лежать открытыми не должны.
"""

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin
from app.security import decrypt_bot_token, encrypt_bot_token

# Тип реквизита. Влияет только на подпись и подсказку в интерфейсе — платформа
# не проверяет ни номер карты, ни адрес кошелька: перевод идёт мимо неё.
KINDS = ("card", "sbp", "crypto", "other")


class ShopPaymentMethod(Base, CreatedAtMixin):
    __tablename__ = "shop_payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )

    kind: Mapped[str] = mapped_column(String(16), default="card")
    # Что это за счёт словами продавца: «Сбербанк», «Т-Банк», «USDT TRC20»
    label: Mapped[str] = mapped_column(String(64))
    # Номер карты / телефон / адрес кошелька и имя получателя — шифрованные
    account_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    holder_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    # «В назначении укажи номер заказа» — свободная строка от продавца
    note: Mapped[str | None] = mapped_column(String(200))
    # Выключенный способ не предлагается на чекауте, но остаётся в снимках
    # уже оформленных заказов
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bot = relationship("SellerBot")

    @property
    def account(self) -> str:
        return decrypt_bot_token(self.account_encrypted)

    @account.setter
    def account(self, value: str) -> None:
        self.account_encrypted = encrypt_bot_token(value)

    @property
    def holder(self) -> str | None:
        return decrypt_bot_token(self.holder_encrypted) if self.holder_encrypted else None

    @holder.setter
    def holder(self, value: str | None) -> None:
        self.holder_encrypted = encrypt_bot_token(value) if value else None

    def snapshot(self) -> dict:
        """Что уезжает в заказ. Снимок, а не ссылка: продавец переименует или
        удалит способ, а в старом заказе должно остаться то, куда реально
        переводили (та же причина, что у variant_title в OrderItem)."""
        return {
            "kind": self.kind,
            "label": self.label,
            "account": self.account,
            "holder": self.holder,
            "note": self.note,
        }
