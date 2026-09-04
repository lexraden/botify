"""payout batches

Выплаты копятся и уходят одним transfer'ом: у Crypto Pay есть минимальная
сумма перевода, которую одна продажа обычно не набирает.

Revision ID: 7c41ab90ef21
Revises: 6158daf99d33
Create Date: 2026-08-21 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7c41ab90ef21'
down_revision = '6158daf99d33'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payout_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('last_error', sa.String(length=512), nullable=True),
        sa.Column('transfer_id', sa.BigInteger(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transfer_id'),
    )
    op.create_index(op.f('ix_payout_batches_seller_id'), 'payout_batches', ['seller_id'])
    op.create_index(op.f('ix_payout_batches_status'), 'payout_batches', ['status'])

    op.add_column('payouts', sa.Column('batch_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_payouts_batch_id'), 'payouts', ['batch_id'])
    op.create_foreign_key(
        'fk_payouts_batch_id', 'payouts', 'payout_batches', ['batch_id'], ['id'], ondelete='SET NULL'
    )
    # transfer_id теперь общий для всей пачки — уникальность снимаем
    op.execute('ALTER TABLE payouts DROP CONSTRAINT IF EXISTS payouts_transfer_id_key')

    # Незавершённые выплаты, которые успели уйти в failed из-за AMOUNT_TOO_SMALL,
    # возвращаем в pending: теперь они дождутся своей пачки, а не будут
    # ретраиться поштучно и слать продавцу ошибку каждый час.
    op.execute(
        "UPDATE payouts SET status = 'pending' "
        "WHERE status = 'failed' AND (last_error ILIKE '%AMOUNT_TOO_SMALL%' "
        "OR last_error ILIKE '%MIN_AMOUNT%')"
    )


def downgrade() -> None:
    op.drop_constraint('fk_payouts_batch_id', 'payouts', type_='foreignkey')
    op.drop_index(op.f('ix_payouts_batch_id'), table_name='payouts')
    op.drop_column('payouts', 'batch_id')
    op.create_unique_constraint('payouts_transfer_id_key', 'payouts', ['transfer_id'])
    op.drop_index(op.f('ix_payout_batches_status'), table_name='payout_batches')
    op.drop_index(op.f('ix_payout_batches_seller_id'), table_name='payout_batches')
    op.drop_table('payout_batches')
