"""Фото в relay-чате: chat_images + chat_messages.image_token (и в архиве)

Картинки переписки хранятся в БД по образцу product_images: случайный
token-адрес вместо порядкового id, тип из белого списка, байты не больше
5 МБ. У сообщений появляется необязательная ссылка на картинку; у фото без
подписи body остаётся пустой строкой (колонка NOT NULL не меняется).

Revision ID: d8e9f0a1b2c3
Revises: c4d5e6f7a8b9
Create Date: 2026-08-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd8e9f0a1b2c3'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chat_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column(
            'bot_id',
            sa.Integer(),
            sa.ForeignKey('seller_bots.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'chat_id',
            sa.Integer(),
            sa.ForeignKey('order_chats.id', ondelete='CASCADE'),
            nullable=False,
        ),
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
    op.create_index(op.f('ix_chat_images_token'), 'chat_images', ['token'], unique=True)
    op.create_index(op.f('ix_chat_images_bot_id'), 'chat_images', ['bot_id'])
    op.create_index(op.f('ix_chat_images_chat_id'), 'chat_images', ['chat_id'])

    op.add_column(
        'chat_messages',
        sa.Column('image_token', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'chat_messages_archive',
        sa.Column('image_token', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('chat_messages_archive', 'image_token')
    op.drop_column('chat_messages', 'image_token')
    op.drop_index(op.f('ix_chat_images_chat_id'), table_name='chat_images')
    op.drop_index(op.f('ix_chat_images_bot_id'), table_name='chat_images')
    op.drop_index(op.f('ix_chat_images_token'), table_name='chat_images')
    op.drop_table('chat_images')
