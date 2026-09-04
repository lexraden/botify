"""Аватар бота: фото магазина на витрине

bot_avatars хранит скачанное из Telegram фото бота (логотип магазина) в БД —
по образцу product_images. Один аватар на магазин (bot_id UNIQUE), адрес —
случайный токен с immutable-кэшем; при обновлении строка заменяется целиком.

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-25 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'g2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bot_avatars',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('mime', sa.String(length=32), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['bot_id'], ['seller_bots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_id', name='uq_bot_avatar_one_per_bot'),
    )
    op.create_index('ix_bot_avatars_bot_id', 'bot_avatars', ['bot_id'])
    op.create_index('ix_bot_avatars_token', 'bot_avatars', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_bot_avatars_token', table_name='bot_avatars')
    op.drop_index('ix_bot_avatars_bot_id', table_name='bot_avatars')
    op.drop_table('bot_avatars')
