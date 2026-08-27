"""Признак бота, созданного кнопкой платформы (managed bot)

Нужен для восстановления: если продавец перевыпустит токен своего бота в
@BotFather, наш вебхук отвалится. Бота, созданного через нашу кнопку, мы можем
починить сами — `replaceManagedBotToken` выдаёт платформе новый токен без
участия человека. Боту, подключённому вручную токеном, так нельзя: там мы
никем не управляем и остаётся только просить новый токен у продавца.

Из существующих полей это не выводится — токен, юзернейм и telegram_bot_id у
обоих способов подключения выглядят одинаково.

Всем существующим ботам ставится false: до этой ветки кнопки создания не было,
значит все они подключены вручную.

Revision ID: o0a1b2c3d4e5
Revises: n9f0a1b2c3d4
Create Date: 2026-08-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'o0a1b2c3d4e5'
down_revision = 'n9f0a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'seller_bots',
        sa.Column(
            'is_managed',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column('seller_bots', 'is_managed')
