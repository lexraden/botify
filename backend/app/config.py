from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    hub_bot_token: str
    webhook_base_url: str = ""  # пусто = локальная разработка без вебхуков
    telegram_webhook_secret: str

    database_url: str

    crypto_pay_token: str = ""
    crypto_pay_network: str = "mainnet"  # mainnet | testnet (@CryptoTestnetBot)
    # Минимальная сумма одного transfer в Crypto Pay: замерена через
    # /testpayout — ниже 2 USDT перевод отбивается с AMOUNT_TOO_SMALL.
    # Меньше этого выплаты копятся и уходят пачкой (app/payments/payouts.py).
    min_payout_usdt: float = 2.0
    # Комиссия самого Crypto Pay за приём платежа. Точное значение приходит
    # в вебхуке (fee_amount) — это оценка на случай, если его там нет.
    crypto_pay_fee_pct: float = 3.0

    # Ключ Fernet: токены seller-ботов никогда не хранятся в БД открытым текстом
    bot_token_encryption_key: str

    webapp_url: str = ""

    admin_telegram_ids: str = ""
    platform_commission_pct: float = 5.0

    # Лимиты бесплатного тарифа (см. app/plans.py). Пока False — лимиты
    # только считаются и показываются, но ничего не блокируют.
    enforce_plan_limits: bool = False

    @field_validator("database_url")
    @classmethod
    def force_asyncpg(cls, v: str) -> str:
        # Railway выдаёт postgresql:// — приводим к async-драйверу
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def effective_webapp_url(self) -> str:
        # витрину раздаёт сам бэкенд — отдельный WEBAPP_URL нужен только
        # если фронт хостится отдельно
        return self.webapp_url or self.webhook_base_url

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_telegram_ids.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
