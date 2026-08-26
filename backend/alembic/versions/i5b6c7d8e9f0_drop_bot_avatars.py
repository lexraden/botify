"""Убрана таблица bot_avatars: аватар магазина из Telegram не читается

Аватар бота тянулся через `get_chat(telegram_bot_id)` — бот спрашивал Telegram
про самого себя. `getChat` для приватного чата отвечает, только если этот
пользователь с ботом уже взаимодействовал, а сам себе бот написать не может:
ожидаемый ответ — `chat not found`. Метода, который вернул бы боту его
собственную аватарку, в Bot API нет вовсе (`getMyName`, `getMyDescription`,
`getMyCommands` есть, `getMyPhoto` — нет; картинка бота живёт в @BotFather).
Функция не работала в проде и убрана целиком; в шапке витрины остаётся буква
юзернейма.

Таблица пустая по той же причине — падение скачивания не создавало строк,
поэтому данные не теряются. downgrade возвращает схему как было.

Revision ID: i5b6c7d8e9f0
Revises: h4a5b6c7d8e9
Create Date: 2026-08-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'i5b6c7d8e9f0'
down_revision = 'h4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f('ix_bot_avatars_token'), table_name='bot_avatars')
    op.drop_index(op.f('ix_bot_avatars_bot_id'), table_name='bot_avatars')
    op.drop_table('bot_avatars')


def downgrade() -> None:
    op.create_table(
        'bot_avatars',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'bot_id',
            sa.Integer(),
            sa.ForeignKey('seller_bots.id', ondelete='CASCADE'),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bot_avatars_bot_id'), 'bot_avatars', ['bot_id'], unique=True)
    op.create_index(op.f('ix_bot_avatars_token'), 'bot_avatars', ['token'], unique=True)
