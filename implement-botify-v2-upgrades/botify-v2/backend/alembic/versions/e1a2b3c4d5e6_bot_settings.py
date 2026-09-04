"""bot settings: welcome text and catalog button

Настройки seller-бота из /settings: приветствие покупателю на /start
и кнопка открытия витрины (вкл/выкл + свой текст).

Revision ID: e1a2b3c4d5e6
Revises: c93e1f80b7d2
Create Date: 2026-08-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e1a2b3c4d5e6'
down_revision = 'c93e1f80b7d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('seller_bots', sa.Column('welcome_text', sa.Text(), nullable=True))
    # существующим ботам — текущее поведение: кнопка включена
    op.add_column(
        'seller_bots',
        sa.Column('show_catalog_button', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        'seller_bots',
        sa.Column('catalog_button_text', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('seller_bots', 'catalog_button_text')
    op.drop_column('seller_bots', 'show_catalog_button')
    op.drop_column('seller_bots', 'welcome_text')
