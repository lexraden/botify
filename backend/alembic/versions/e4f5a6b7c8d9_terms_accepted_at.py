"""terms accepted at

Факт принятия условий использования на первом экране онбординга: таймстамп
в профиле продавца. NULL = ещё не принял; существующие продавцы остаются
NULL — принудительного повторного согласия у них не требуется.

Revision ID: e4f5a6b7c8d9
Revises: b3c2d1e0f9a8
Create Date: 2026-08-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4f5a6b7c8d9'
down_revision = 'b3c2d1e0f9a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sellers', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('sellers', 'terms_accepted_at')
