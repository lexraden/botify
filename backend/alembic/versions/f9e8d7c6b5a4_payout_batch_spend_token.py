"""payout_batches.spend_id: случайный токен transfer'а вместо batch-{id}

spend_id в Crypto Pay должен быть уникальным навсегда, а batch-{id} зависел
от порядкового номера пачки: после сброса базы нумерация начинается заново
и новый перевод отбивается с SPEND_ID_ALREADY_USED. Теперь токен хранится
в самой пачке и не меняется при ретраях.

Revision ID: f9e8d7c6b5a4
Revises: e4f5a6b7c8d9
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa


revision = "f9e8d7c6b5a4"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # nullable -> бэкфилл -> NOT NULL: таблица может быть непустой.
    # Бэкфилл значением batch-{id}: существующие пачки уже ходили в Crypto Pay
    # именно с таким spend_id — он должен остаться прежним, иначе повторная
    # отправка старой пачки считалась бы новой выплатой.
    op.add_column("payout_batches", sa.Column("spend_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE payout_batches SET spend_id = 'batch-' || id")
    # batch_alter_table: на Postgres это обычные ALTER, а на SQLite —
    # пересоздание таблицы (нативный ALTER COLUMN там не поддерживается)
    with op.batch_alter_table("payout_batches") as batch_op:
        batch_op.alter_column("spend_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint("uq_payout_batches_spend_id", ["spend_id"])


def downgrade() -> None:
    # через batch: на SQLite нативный DROP COLUMN запрещён для столбца с
    # UNIQUE — таблица пересоздаётся без него; на Postgres это обычный ALTER
    with op.batch_alter_table("payout_batches") as batch_op:
        batch_op.drop_column("spend_id")
