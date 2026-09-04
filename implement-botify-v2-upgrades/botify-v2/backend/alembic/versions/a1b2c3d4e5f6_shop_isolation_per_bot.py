"""One bot = one shop: scope catalog and orders to seller_bots

Каждый подключённый бот продавца — отдельный изолированный магазин со своим
каталогом, заказами и базой покупателей. Раньше products/categories/orders
были привязаны только к seller_id и шарились между ботами одного продавца.

Плюс новые значения onboarding_step (онбординг переехал в Mini App).

Revision ID: a1b2c3d4e5f6
Revises: 3d726f7913b5
Create Date: 2026-08-19

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '3d726f7913b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. bot_id в каталоге и заказах (сначала nullable, потом бэкфилл) ---
    op.add_column('categories', sa.Column('bot_id', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('bot_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('bot_id', sa.Integer(), nullable=True))

    # Заказы: магазин берём у покупателя — он всегда привязан к конкретному боту
    op.execute(
        "UPDATE orders o SET bot_id = c.bot_id FROM customers c WHERE c.id = o.customer_id"
    )
    # Каталог: отдаём первому (самому старому) боту продавца
    for table in ('categories', 'products'):
        op.execute(
            f"UPDATE {table} t SET bot_id = ("
            "  SELECT MIN(b.id) FROM seller_bots b WHERE b.seller_id = t.seller_id"
            ")"
        )
        # Строки продавцов без единого бота недостижимы из витрины — удаляем
        op.execute(f"DELETE FROM {table} WHERE bot_id IS NULL")
    # Заказ без покупателя невозможен, но подстрахуемся
    op.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE bot_id IS NULL)")
    op.execute("DELETE FROM payouts WHERE order_id IN (SELECT id FROM orders WHERE bot_id IS NULL)")
    op.execute("DELETE FROM orders WHERE bot_id IS NULL")

    op.alter_column('categories', 'bot_id', nullable=False)
    op.alter_column('products', 'bot_id', nullable=False)
    op.alter_column('orders', 'bot_id', nullable=False)

    op.create_index(op.f('ix_categories_bot_id'), 'categories', ['bot_id'])
    op.create_index(op.f('ix_products_bot_id'), 'products', ['bot_id'])
    op.create_index(op.f('ix_orders_bot_id'), 'orders', ['bot_id'])
    op.create_foreign_key(
        'fk_categories_bot_id', 'categories', 'seller_bots', ['bot_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_products_bot_id', 'products', 'seller_bots', ['bot_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_orders_bot_id', 'orders', 'seller_bots', ['bot_id'], ['id'], ondelete='RESTRICT'
    )

    # --- 2. Новые значения onboarding_step ---
    op.execute(
        "UPDATE sellers SET onboarding_step = CASE "
        "  WHEN onboarding_step = 'done' THEN 'bot_done' "
        "  WHEN onboarding_step = 'bot_connect' THEN 'bot_pending' "
        "  WHEN cryptobot_connected THEN 'bot_pending' "
        "  ELSE 'payment_pending' END"
    )
    op.alter_column('sellers', 'onboarding_step', server_default='payment_pending')


def downgrade() -> None:
    op.execute(
        "UPDATE sellers SET onboarding_step = CASE "
        "  WHEN onboarding_step = 'bot_done' THEN 'done' "
        "  WHEN onboarding_step = 'bot_pending' THEN 'bot_connect' "
        "  ELSE 'none' END"
    )
    op.drop_constraint('fk_orders_bot_id', 'orders', type_='foreignkey')
    op.drop_constraint('fk_products_bot_id', 'products', type_='foreignkey')
    op.drop_constraint('fk_categories_bot_id', 'categories', type_='foreignkey')
    op.drop_index(op.f('ix_orders_bot_id'), table_name='orders')
    op.drop_index(op.f('ix_products_bot_id'), table_name='products')
    op.drop_index(op.f('ix_categories_bot_id'), table_name='categories')
    op.drop_column('orders', 'bot_id')
    op.drop_column('products', 'bot_id')
    op.drop_column('categories', 'bot_id')
