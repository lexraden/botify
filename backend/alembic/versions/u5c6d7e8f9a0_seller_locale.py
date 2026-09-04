"""Ручной выбор языка hub-бота: sellers.locale.

Revision ID: u5c6d7e8f9a0
Revises: t4b5c6d7e8f9
Create Date: 2026-08-29

None = язык не выбран, тогда язык берётся из language_code по правилу
seller_texts.seller_locale. Колонка nullable без серверного дефолта — как
customers.locale (p1a2b3c4d5e6).
"""

from alembic import op
import sqlalchemy as sa

revision = "u5c6d7e8f9a0"
down_revision = "t4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sellers", sa.Column("locale", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("sellers", "locale")
