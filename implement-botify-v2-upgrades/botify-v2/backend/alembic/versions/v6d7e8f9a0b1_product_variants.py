"""Вариации товара: цвет, размер, комплектация — со своей ценой и остатком

Товар до сих пор был одной строкой с одной ценой и одним остатком. Продать
футболку в трёх размерах можно было только тремя отдельными товарами: каталог
раздувался, а покупатель видел три карточки одного и того же.

Вариация держит своё: артикул, свойства, цену (и зачёркнутую «старую»),
остаток и свои фотографии. Товар без вариаций остаётся ровно таким, каким был —
таблица пустая, и ни один существующий запрос не меняется.

`products.price` и `products.stock` не выключаются: при сохранении товара с
вариациями цена пересчитывается в минимальную («от 500»), остаток — в сумму.
Поэтому витрина, карточки, статистика и сверка платежей продолжают читать товар
как раньше.

`order_items.variant_id` — какую вариацию купили; `variant_label` — снимок её
свойств на момент покупки, по той же причине, по которой снимается цена:
продавец переименует размеры, а в старом заказе должно остаться купленное.

Revision ID: v6d7e8f9a0b1
Revises: u5c6d7e8f9a0
Create Date: 2026-08-29 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'v6d7e8f9a0b1'
down_revision = 'u5c6d7e8f9a0'
branch_labels = None
depends_on = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        'product_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(length=64), nullable=True),
        sa.Column('attributes', JsonB, nullable=True),
        sa.Column('price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('compare_at_price', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('stock', sa.Integer(), nullable=True),
        sa.Column('images', JsonB, nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bot_id'], ['seller_bots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_product_variants_product_id', 'product_variants', ['product_id'])
    op.create_index('ix_product_variants_bot_id', 'product_variants', ['bot_id'])

    # RESTRICT, как и product_id: удалить вариацию, которую уже купили, нельзя —
    # иначе из заказа пропадёт то, за что человек заплатил
    op.add_column('order_items', sa.Column('variant_id', sa.Integer(), nullable=True))
    op.add_column('order_items', sa.Column('variant_label', sa.String(length=128), nullable=True))
    op.create_foreign_key(
        'fk_order_items_variant_id', 'order_items', 'product_variants',
        ['variant_id'], ['id'], ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_order_items_variant_id', 'order_items', type_='foreignkey')
    op.drop_column('order_items', 'variant_label')
    op.drop_column('order_items', 'variant_id')
    op.drop_index('ix_product_variants_bot_id', table_name='product_variants')
    op.drop_index('ix_product_variants_product_id', table_name='product_variants')
    # вместе с таблицей уходят вариации; товары остаются со своей ценой и
    # остатком, которые всё это время держались в актуальном состоянии
    op.drop_table('product_variants')
