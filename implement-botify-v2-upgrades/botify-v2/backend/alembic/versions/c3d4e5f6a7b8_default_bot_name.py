"""Исходное Telegram-имя бота: seller_bots.default_bot_name

Имя и лого магазина теперь уезжают в профиль самого бота (setMyName /
setMyProfilePhoto, services/bot_profile.py). Чтобы сброс имени (shop_name =
null) возвращал боту прежнее Telegram-имя, а не оставлял последнее заданное,
исходное имя запоминается при подключении: getMe.first_name у ручного бота,
имя из managed_bot_created у созданного через платформу.

Колонка nullable намеренно и без бэкфилла: у ботов, подключённых до этой
миграции, исходное имя восстановить неоткуда (getMe сейчас вернёт уже
текущее имя, которое могло быть задано продавцом), и при сбросе они просто
не переименовываются. Заполнится при следующем подключении/переподключении.

Проверена up -> down -> up на пустой базе.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'seller_bots',
        sa.Column('default_bot_name', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('seller_bots', 'default_bot_name')
