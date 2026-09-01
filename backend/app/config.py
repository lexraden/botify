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

    # Лимиты бесплатного тарифа (см. app/plans.py). Включаются вместе с
    # платной подпиской: блокировать рост, не дав способа заплатить, нельзя.
    enforce_plan_limits: bool = False

    # Pro-подписка продавца (app/plans.py, app/payments/subscription.py).
    # Цена в звёздах — отдельное число, а не пересчёт из USDT: курса звезды
    # в API Telegram нет, и «автоматическая сверка» тут была бы выдумкой.
    # 1500 звёзд подобраны так, чтобы платформа получила на выводе примерно
    # те же 20 USDT (решение владельца от 2026-08-31).
    pro_price_usdt: float = 20.0
    pro_price_stars: int = 1500
    # Plus = Pro плюс приём оплаты по реквизитам продавца в чате заказа.
    # Звёзды пересчитаны по той же пропорции, что владелец выбрал для Pro
    # (1500 звёзд за 20 USDT), чтобы выручка платформы совпадала.
    plus_price_usdt: float = 50.0
    plus_price_stars: int = 3750
    pro_period_days: int = 30
    # За сколько дней до конца подписки напомнить продавцу
    pro_reminder_days: int = 3

    # Окно активности чата заказа (app/services/chat.py): после доставки
    # заказ можно обсуждать ещё 72 часа, потом чат закрывается для новых
    # сообщений (история остаётся читаемой).
    chat_window_hours: float = 72.0
    # Через сколько дней после блокировки история уходит в архивную таблицу
    archive_chat_after_days: int = 30

    # Обслуживание (app/main.py: maintenance_loop)
    # Через сколько часов после оплаты напомнить продавцу о неотправленном
    # заказе (app/services/order_health.py). Напоминание одно на заказ.
    stuck_order_hours: float = 24.0
    # Как часто проверять, не отозван ли токен seller-бота
    # (app/services/bot_health.py). Один get_me на бота за проход.
    token_check_hours: float = 1.0
    # После скольких минут без признака жизни рассылка в статусе sending
    # считается застрявшей и возвращается в очередь
    mailing_stuck_minutes: int = 10
    # Глубина сверки оплаченных счетов (app/payments/reconcile.py): счёт
    # живёт час, окно — с запасом на задержки вебхука и наши рестарты.
    reconcile_window_hours: float = 6.0

    # Через сколько дней отправленный заказ считается полученным, если
    # покупатель не нажал «Получил» (app/services/order_health.py). С запасом
    # на долгую доставку: раньше времени закрывать окно чата нельзя.
    auto_deliver_days: int = 21

    # Сколько минут неоплаченный заказ ждёт оплату (app/services/order_health.py):
    # дефолт совпадает с жизнью инвойса в Crypto Pay (3600 с). Выписали новый
    # счёт по кнопке «Оплатить» — заказу даётся столько же заново.
    unpaid_order_ttl_minutes: int = 60

    # Модерация отзывов (app/services/reviews.py): оценка >= порога публикуется
    # сразу, ниже — ждёт одобрения продавца во вкладке «Отзывы». Не
    # отмодерированное продавцом публикуется само через review_moderation_days
    # (джоб в maintenance_loop): молчание продавца не прячет отзыв навсегда.
    review_auto_publish_min: int = 4
    review_moderation_days: int = 7

    # Куда ведёт «Поддержка» в профиле покупателя. Пусто — кнопки нет вовсе:
    # раньше она вела в hub-бот, то есть покупателя с проблемой по заказу
    # регистрировали продавцом и показывали ему рекламу конструктора ботов.
    support_url: str = ""

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
