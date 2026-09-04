"""product images table

Фото товаров хранятся в БД (Railway-контейнер эфемерен, объектного хранилища
у проекта нет). Тип файла фиксируется по содержимому при загрузке.

Revision ID: b3c2d1e0f9a8
Revises: f7a8b9c0d1e2
Create Date: 2026-08-22 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c2d1e0f9a8'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'product_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=False),
        sa.Column('mime', sa.String(length=32), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bot_id'], ['seller_bots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_images_bot_id'), 'product_images', ['bot_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_product_images_bot_id'), table_name='product_images')
    op.drop_table('product_images')
