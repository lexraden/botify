import os

from cryptography.fernet import Fernet

# Настройки окружения ДО импорта app.* (config/engine создаются при импорте)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://botify:botify@localhost:5432/botify_test"
)
os.environ["HUB_BOT_TOKEN"] = "123456:TEST-token-for-tests-only"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "test-secret"
os.environ["BOT_TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["WEBHOOK_BASE_URL"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.db import engine, session_factory  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def db():
    """Чистая схема на каждый тест."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield session_factory
    # каждый тест живёт в своём event loop — пул нельзя переносить между ними
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_managed_bots_cache():
    """Флаг «нам можно создавать ботов» кэшируется на пять минут
    (app/services/shop_draft.py). В тестах ответ Telegram подменяется, и без
    сброса соседний тест получал бы чужой закэшированный ответ."""
    from app.services.shop_draft import reset_managed_cache

    reset_managed_cache()
    yield
    reset_managed_cache()
