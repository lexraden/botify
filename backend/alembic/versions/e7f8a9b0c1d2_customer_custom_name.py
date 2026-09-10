"""Имя покупателя, заданное им самим в Mini App

Покупатель теперь может поменять своё имя в профиле приложения. Колонка
`customers.custom_name` хранит именно его; имя из Telegram (`first_name`)
продолжает жить отдельно и синхронизироваться при каждом визите — писать
правку туда было нельзя, upsert_customer затёр бы её первым же запросом.

NULL — покупатель имя не менял: показывается Telegram-имя, пустая правка
в профиле возвращает к нему же.

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c1
Create Date: 2026-09-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e7f8a9b0c1d2'
down_revision = 'd5e6f7a8b9c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'customers',
        sa.Column('custom_name', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('customers', 'custom_name')
