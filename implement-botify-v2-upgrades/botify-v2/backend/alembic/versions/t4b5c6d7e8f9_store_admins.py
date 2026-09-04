"""Администраторы магазина: store_admins

Владелец приглашает продавца вести магазин: связь (бот, продавец) с ролью.
Уникальность пары защищает от двойной выдачи; оба FK каскадные — удаление
магазина или продавца уносит и выданные роли. Бэкфилл не нужен: роли
выдаются только через новый интерфейс, существующих админов нет.

Revision ID: t4b5c6d7e8f9
Revises: r3c4d5e6f7g8
Create Date: 2026-08-29 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 't4b5c6d7e8f9'
down_revision = 'r3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'store_admins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'bot_id',
            sa.Integer(),
            sa.ForeignKey('seller_bots.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'seller_id',
            sa.Integer(),
            sa.ForeignKey('sellers.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('role', sa.String(length=32), server_default='admin', nullable=False),
        # CURRENT_TIMESTAMP, а не now(): валидно и в Postgres, и в SQLite
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_id', 'seller_id', name='uq_store_admins_bot_seller'),
    )
    op.create_index(op.f('ix_store_admins_bot_id'), 'store_admins', ['bot_id'])
    op.create_index(op.f('ix_store_admins_seller_id'), 'store_admins', ['seller_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_store_admins_seller_id'), table_name='store_admins')
    op.drop_index(op.f('ix_store_admins_bot_id'), table_name='store_admins')
    op.drop_table('store_admins')
