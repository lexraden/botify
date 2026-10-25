import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from app.models import Base

load_dotenv()

config = context.config

# DATABASE_URL из окружения; alembic работает через sync-драйвер
url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError(
        "DATABASE_URL is not set. On Railway: add a PostgreSQL database to the "
        "project and set service variable DATABASE_URL=${{Postgres.DATABASE_URL}}."
    )
# Драйвер — явно psycopg2 (он и стоит в requirements). Голое «postgresql://»
# в SQLAlchemy 2.1 значит уже psycopg третьей версии, которого у нас нет:
# миграция падала на ModuleNotFoundError, а Railway запускает сервис командой
# «alembic upgrade head && uvicorn» — приложение не поднималось бы вовсе.
# Railway отдаёт адрес именно голым postgresql://, приложение — с +asyncpg.
for prefix in ("postgresql+asyncpg://", "postgresql://"):
    if url.startswith(prefix):
        url = "postgresql+psycopg2://" + url[len(prefix):]
        break
config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
