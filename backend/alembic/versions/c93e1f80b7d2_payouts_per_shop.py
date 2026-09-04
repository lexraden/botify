"""payouts per shop

Касса у каждого подключённого бота своя: выплаты копятся и выводятся
по магазину, а не по продавцу целиком (docs/project-brief.md, п. 8.3).

Revision ID: c93e1f80b7d2
Revises: b52d0c7f1a34
Create Date: 2026-08-21 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c93e1f80b7d2'
down_revision = 'b52d0c7f1a34'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Колонки заводим nullable — сначала заполним, потом закрутим NOT NULL
    op.add_column('payouts', sa.Column('bot_id', sa.Integer(), nullable=True))
    op.add_column('payout_batches', sa.Column('bot_id', sa.Integer(), nullable=True))

    # 2. Бэкфилл: у выплаты магазин берётся из её заказа
    op.execute(
        "UPDATE payouts p SET bot_id = o.bot_id FROM orders o WHERE o.id = p.order_id"
    )
    # у пачки — из любой входящей в неё выплаты
    op.execute(
        "UPDATE payout_batches b SET bot_id = ("
        "  SELECT p.bot_id FROM payouts p WHERE p.batch_id = b.id LIMIT 1)"
    )
    # пачка без выплат (все распущены) — вешаем на первый бот её продавца,
    # такие пачки уже завершены и на деньги не влияют
    op.execute(
        "UPDATE payout_batches b SET bot_id = ("
        "  SELECT sb.id FROM seller_bots sb WHERE sb.seller_id = b.seller_id"
        "  ORDER BY sb.id LIMIT 1) WHERE b.bot_id IS NULL"
    )
    # продавец без единого бота выплат иметь не может, но подстрахуемся:
    # такие пачки удалять нельзя, поэтому оставляем их вне выборок
    op.execute("DELETE FROM payout_batches WHERE bot_id IS NULL")

    op.alter_column('payouts', 'bot_id', nullable=False)
    op.alter_column('payout_batches', 'bot_id', nullable=False)

    op.create_index(op.f('ix_payouts_bot_id'), 'payouts', ['bot_id'])
    op.create_index(op.f('ix_payout_batches_bot_id'), 'payout_batches', ['bot_id'])
    op.create_foreign_key(
        'fk_payouts_bot_id', 'payouts', 'seller_bots', ['bot_id'], ['id'], ondelete='RESTRICT'
    )
    op.create_foreign_key(
        'fk_payout_batches_bot_id',
        'payout_batches',
        'seller_bots',
        ['bot_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_payout_batches_bot_id', 'payout_batches', type_='foreignkey')
    op.drop_constraint('fk_payouts_bot_id', 'payouts', type_='foreignkey')
    op.drop_index(op.f('ix_payout_batches_bot_id'), table_name='payout_batches')
    op.drop_index(op.f('ix_payouts_bot_id'), table_name='payouts')
    op.drop_column('payout_batches', 'bot_id')
    op.drop_column('payouts', 'bot_id')
