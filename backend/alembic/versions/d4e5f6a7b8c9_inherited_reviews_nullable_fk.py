"""Наследуемые отзывы: nullable order_id/customer_id + source + частичная уникальность

При копии магазина (бот забанен, переезд) переносим отзывы без заказов/покупателей:
- order_id, customer_id становятся nullable — наследуемые отзывы создаются без них
- Колонка source ('normal' | 'inherited') — различает родные и скопированные отзывы
- Частичный уникальный индекс: (order_id, product_id) уникально только для order_id IS NOT NULL
  (в PostgreSQL NULL != NULL, поэтому обычный UNIQUE позволял бы бесконечные дубли с NULL)

Бэкфилл: существующие отзывы получают source='normal' (server_default).
"""

from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'z0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Делаем FK nullable
    op.alter_column(
        'product_reviews', 'order_id',
        existing_type=sa.Integer(),
        nullable=True
    )
    op.alter_column(
        'product_reviews', 'customer_id',
        existing_type=sa.Integer(),
        nullable=True
    )

    # 2. Добавляем колонку source с дефолтом 'normal' для существующих строк
    op.add_column(
        'product_reviews',
        sa.Column(
            'source', sa.String(length=16),
            nullable=False, server_default='normal'
        )
    )

    # 3. Частичный уникальный индекс: уникальность только для нормальных отзывов
    # (наследуемые с order_id=NULL не попадают под ограничение)
    op.execute("""
        CREATE UNIQUE INDEX uq_review_once_per_order_item_partial
        ON product_reviews (order_id, product_id)
        WHERE order_id IS NOT NULL
    """)

    # Старый констрейнт uq_review_once_per_order_item остаётся —
    # частичный индекс перекрывает его логику для NULL, а для NOT NULL
    # оба работают одинаково. Можно дропнуть старый, но он не мешает.


def downgrade() -> None:
    # 1. Удаляем частичный индекс
    op.execute("DROP INDEX IF EXISTS uq_review_once_per_order_item_partial")

    # 2. Удаляем колонку source
    op.drop_column('product_reviews', 'source')

    # 3. Возвращаем NOT NULL (требует, чтобы order_id/customer_id не были NULL)
    op.alter_column(
        'product_reviews', 'order_id',
        existing_type=sa.Integer(),
        nullable=False
    )
    op.alter_column(
        'product_reviews', 'customer_id',
        existing_type=sa.Integer(),
        nullable=False
    )