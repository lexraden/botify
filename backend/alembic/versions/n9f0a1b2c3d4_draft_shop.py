"""Черновик магазина: seller_bots до подключения бота + название магазина

Онбординг начинается с названия, а бот подключается последним. Значит магазин
должен уметь существовать раньше бота, а сегодня не может: токен, юзернейм и
telegram_bot_id объявлены NOT NULL.

Отдельной сущности «черновик» не заводим. Это та же строка `seller_bots` с
пустым токеном — и `bot_id` появляется сразу, поэтому товары, витрина и вся
изоляция по bot_id работают без единой правки. Признак черновика —
`bot_token_encrypted IS NULL`, отдельного флага нет намеренно: он был бы вторым
источником правды о том же самом.

`title` — название магазина. Нужно не для красоты: из него собираются
suggested_name и suggested_username для кнопки создания бота
(app/services/shop_draft.py), и оно же показывается в шапке витрины.

Существующим магазинам title бэкфиллится юзернеймом бота: другого названия
у них никогда не было.

Revision ID: n9f0a1b2c3d4
Revises: m8e9f0a1b2c3
Create Date: 2026-08-26 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'n9f0a1b2c3d4'
down_revision = 'm8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('seller_bots', sa.Column('title', sa.String(length=128), nullable=True))
    op.execute("UPDATE seller_bots SET title = bot_username WHERE title IS NULL")

    # до подключения бота этих значений просто нет
    op.alter_column(
        'seller_bots', 'bot_token_encrypted', existing_type=sa.LargeBinary(), nullable=True
    )
    op.alter_column('seller_bots', 'bot_username', existing_type=sa.String(length=64), nullable=True)
    op.alter_column('seller_bots', 'telegram_bot_id', existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    # черновиков в старой схеме быть не может — удаляем, иначе NOT NULL не встанет
    op.execute("DELETE FROM seller_bots WHERE bot_token_encrypted IS NULL")
    op.alter_column('seller_bots', 'telegram_bot_id', existing_type=sa.BigInteger(), nullable=False)
    op.alter_column(
        'seller_bots', 'bot_username', existing_type=sa.String(length=64), nullable=False
    )
    op.alter_column(
        'seller_bots', 'bot_token_encrypted', existing_type=sa.LargeBinary(), nullable=False
    )
    op.drop_column('seller_bots', 'title')
