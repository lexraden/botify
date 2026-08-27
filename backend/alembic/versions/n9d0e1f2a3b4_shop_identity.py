"""Имя и логотип магазина: идентичность в шапке витрины

Шапка покупательской витрины показывала только @username бота — ни имени
бренда, ни лого, ни trust-сигналов. Теперь продавец задаёт показное имя
(`shop_name`) и загружает логотип в кабинете; дефолт имени — Telegram-имя
бота из getMe, проставляется при подключении.

Таблица `shop_logos` — зеркало прежней `bot_avatars` (миграции
`g2b3c4d5e6f7` и её удаления `i5b6c7d8e9f0`) по образцу product_images:
один логотип на магазин, адрес — случайный токен с immutable-кэшем.
Обновление целиком удаляет старую строку, поэтому токен всегда меняется
и браузер не отдаёт из кэша старую картинку по адресу новой. Источник
лого — загрузка продавца (в Bot API нет способа прочитать аватарку самого
бота), как предписано записью об удалении bot_avatars.

Revision ID: n9d0e1f2a3b4
Revises: o0a1b2c3d4e5
Create Date: 2026-08-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'n9d0e1f2a3b4'
down_revision = 'o0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'seller_bots',
        sa.Column('shop_name', sa.String(length=64), nullable=True),
    )
    op.create_table(
        'shop_logos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('mime', sa.String(length=32), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['bot_id'], ['seller_bots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_id', name='uq_shop_logo_one_per_bot'),
    )
    op.create_index(op.f('ix_shop_logos_token'), 'shop_logos', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_shop_logos_token'), table_name='shop_logos')
    op.drop_table('shop_logos')
    op.drop_column('seller_bots', 'shop_name')
