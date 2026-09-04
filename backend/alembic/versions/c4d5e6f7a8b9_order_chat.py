"""Relay-чат по заказу: order_chats + chat_messages (+архив), orders.delivered_at

Чат привязан к заказу жёстко (order_id unique) и активируется у оплаченных
заказов. Окно активности — 72 часа после доставки, поэтому заказу нужна метка
времени доставки: delivered_at ставится в момент перехода в 'delivered',
существующим доставленным заказам бэкфилится из paid_at (у digital доставка
совпадает с оплатой, у физических это ближайшая известная точка).

Revision ID: c4d5e6f7a8b9
Revises: a7b8c9d0e1f2
Create Date: 2026-08-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d5e6f7a8b9'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def _chat_message_columns(with_archived_at: bool) -> list[sa.Column]:
    columns = [
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'chat_id',
            sa.Integer(),
            sa.ForeignKey('order_chats.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('sender', sa.String(length=8), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        # message_id сообщения продавца в диалоге покупателя — по ответу-реплаю
        # на него понимаем, к какому заказу относится текст покупателя
        sa.Column('tg_message_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    ]
    if with_archived_at:
        columns.append(sa.Column('archived_at', sa.DateTime(timezone=True), nullable=False))
    return columns


def upgrade() -> None:
    op.add_column('orders', sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE orders SET delivered_at = paid_at WHERE status = 'delivered'")

    op.create_table(
        'order_chats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'order_id',
            sa.Integer(),
            sa.ForeignKey('orders.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'bot_id',
            sa.Integer(),
            sa.ForeignKey('seller_bots.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'seller_id',
            sa.Integer(),
            sa.ForeignKey('sellers.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'customer_id',
            sa.Integer(),
            sa.ForeignKey('customers.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('status', sa.String(length=24), server_default='active', nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_order_chats_order_id'), 'order_chats', ['order_id'], unique=True)
    op.create_index(op.f('ix_order_chats_bot_id'), 'order_chats', ['bot_id'])
    op.create_index(op.f('ix_order_chats_seller_id'), 'order_chats', ['seller_id'])
    op.create_index(op.f('ix_order_chats_customer_id'), 'order_chats', ['customer_id'])

    op.create_table(
        'chat_messages',
        *_chat_message_columns(with_archived_at=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_messages_chat_id'), 'chat_messages', ['chat_id'])
    op.create_index(op.f('ix_chat_messages_tg_message_id'), 'chat_messages', ['tg_message_id'])

    # холодное хранилище: джоб переносит сюда сообщения чатов, заблокированных
    # больше 30 дней назад; чтение истории смотрит в обе таблицы
    op.create_table(
        'chat_messages_archive',
        *_chat_message_columns(with_archived_at=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_messages_archive_chat_id'), 'chat_messages_archive', ['chat_id'])
    op.create_index(
        op.f('ix_chat_messages_archive_tg_message_id'), 'chat_messages_archive', ['tg_message_id']
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_archive_tg_message_id'), table_name='chat_messages_archive')
    op.drop_index(op.f('ix_chat_messages_archive_chat_id'), table_name='chat_messages_archive')
    op.drop_table('chat_messages_archive')
    op.drop_index(op.f('ix_chat_messages_tg_message_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_chat_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_order_chats_customer_id'), table_name='order_chats')
    op.drop_index(op.f('ix_order_chats_seller_id'), table_name='order_chats')
    op.drop_index(op.f('ix_order_chats_bot_id'), table_name='order_chats')
    op.drop_index(op.f('ix_order_chats_order_id'), table_name='order_chats')
    op.drop_table('order_chats')
    op.drop_column('orders', 'delivered_at')
