"""product_images.token + индекс orders.paid_at

Адрес картинки был порядковым id, а отдаётся она с Cache-Control: immutable
на год. После сброса базы нумерация начиналась заново, и браузер показывал
из кэша старую картинку по совпавшему адресу. Теперь адрес — случайный токен,
переиспользоваться он не может.

Заодно индекс на orders.paid_at: оборот за 30 дней в /health был единственным
запросом, который сканирует таблицу заказов целиком и растёт вместе с ней.

Revision ID: a7b8c9d0e1f2
Revises: f9e8d7c6b5a4
Create Date: 2026-08-24 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'f9e8d7c6b5a4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # nullable -> бэкфилл -> NOT NULL: таблица может быть непустой
    op.add_column('product_images', sa.Column('token', sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE product_images SET token = md5(random()::text || clock_timestamp()::text || id::text)"
    )
    op.alter_column('product_images', 'token', existing_type=sa.String(length=64), nullable=False)
    op.create_index(op.f('ix_product_images_token'), 'product_images', ['token'], unique=True)

    # у товаров в image_url лежит старый адрес по id — переписываем на токен,
    # иначе уже загруженные фото перестанут открываться
    op.execute(
        "UPDATE products p SET image_url = '/api/images/' || i.token "
        "FROM product_images i WHERE p.image_url = '/api/images/' || i.id"
    )

    op.create_index(op.f('ix_orders_paid_at'), 'orders', ['paid_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_orders_paid_at'), table_name='orders')
    # адреса товаров возвращаем на id, пока токены ещё на месте
    op.execute(
        "UPDATE products p SET image_url = '/api/images/' || i.id "
        "FROM product_images i WHERE p.image_url = '/api/images/' || i.token"
    )
    op.drop_index(op.f('ix_product_images_token'), table_name='product_images')
    op.drop_column('product_images', 'token')
