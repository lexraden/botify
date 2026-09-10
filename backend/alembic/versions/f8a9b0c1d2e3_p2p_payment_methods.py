"""Оплата переводом на реквизиты продавца (p2p) — функция тарифа Pro

Магазин заводит несколько способов приёма (карта, СБП, крипто-адрес);
покупатель выбирает на чекауте, переводит напрямую продавцу и жмёт
«я оплатил», продавец подтверждает получение. Платформа деньги не держит,
поэтому по таким заказам не создаётся Payout и не берётся комиссия
(решение владельца от 2026-09-10).

Номер счёта и имя получателя шифруются Fernet тем же ключом, что и токены
ботов, — открытыми в базе платёжные данные людей лежать не должны.

В orders три колонки: payment_method (crypto | p2p), payment_details —
снимок выбранных реквизитов (способ могут переименовать или удалить, а в
заказе должно остаться то, куда переводили), и paid_claimed_at — момент,
когда покупатель сказал «оплатил». Последняя заодно снимает заказ с таймера
автоотмены: деньги, возможно, уже ушли.

Бэкфилл не нужен: существующие заказы оплачивались через Crypto Pay, и
server_default='crypto' описывает их верно. После бэкфилла server_default
снимается — способ оплаты обязан приходить из кода явно.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-10 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'f8a9b0c1d2e3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shop_payment_methods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('label', sa.String(length=64), nullable=False),
        sa.Column('account_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('holder_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(['bot_id'], ['seller_bots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_shop_payment_methods_bot_id'), 'shop_payment_methods', ['bot_id'], unique=False
    )

    op.add_column(
        'orders',
        sa.Column('payment_method', sa.String(length=16), nullable=False, server_default='crypto'),
    )
    # server_default снимаем: способ оплаты выбирает чекаут, а INSERT,
    # забывший его указать, не должен молча становиться крипто-заказом
    op.alter_column('orders', 'payment_method', server_default=None)
    op.add_column('orders', sa.Column('payment_details', postgresql.JSONB(), nullable=True))
    op.add_column(
        'orders', sa.Column('paid_claimed_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('orders', 'paid_claimed_at')
    op.drop_column('orders', 'payment_details')
    op.drop_column('orders', 'payment_method')
    op.drop_index(op.f('ix_shop_payment_methods_bot_id'), table_name='shop_payment_methods')
    op.drop_table('shop_payment_methods')
