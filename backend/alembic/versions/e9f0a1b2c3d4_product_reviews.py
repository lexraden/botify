"""Отзывы о товарах: product_reviews

Оценка 1–5 и короткий текст на конкретный товар из доставленного заказа.
Пара (order_id, product_id) уникальна — один отзыв на позицию заказа,
повторная отправка правит существующий. Автор нигде не отдаётся наружу.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-08-25 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e9f0a1b2c3d4'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'product_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'bot_id',
            sa.Integer(),
            sa.ForeignKey('seller_bots.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'product_id',
            sa.Integer(),
            sa.ForeignKey('products.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'order_id',
            sa.Integer(),
            sa.ForeignKey('orders.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'customer_id',
            sa.Integer(),
            sa.ForeignKey('customers.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id', 'product_id', name='uq_review_once_per_order_item'),
    )
    op.create_index(op.f('ix_product_reviews_bot_id'), 'product_reviews', ['bot_id'])
    op.create_index(op.f('ix_product_reviews_product_id'), 'product_reviews', ['product_id'])
    op.create_index(op.f('ix_product_reviews_order_id'), 'product_reviews', ['order_id'])
    op.create_index(op.f('ix_product_reviews_customer_id'), 'product_reviews', ['customer_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_product_reviews_customer_id'), table_name='product_reviews')
    op.drop_index(op.f('ix_product_reviews_order_id'), table_name='product_reviews')
    op.drop_index(op.f('ix_product_reviews_product_id'), table_name='product_reviews')
    op.drop_index(op.f('ix_product_reviews_bot_id'), table_name='product_reviews')
    op.drop_table('product_reviews')
