"""product stock

Остаток товара на складе. NULL — не ограничен (существующие товары и
услуги/digital продолжают жить без учёта штук); списание — в момент оплаты.

Revision ID: f7a8b9c0d1e2
Revises: e1a2b3c4d5e6
Create Date: 2026-08-22 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f7a8b9c0d1e2'
down_revision = 'e1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('products', sa.Column('stock', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'stock')
