"""Своё название и описание у вариации товара

Вариации задумывались как «то же самое, но другого цвета», и название с
описанием оставались товарными. На практике вариациями продают комплектации и
тарифы, у которых расходится и название, и текст — а редактировать их было
негде.

Обе колонки nullable: NULL — брать товарное, ровно так выглядят все вариации,
созданные до этой миграции. Ни одна существующая строка не меняется.

Витрина от этого не меняется: карточка в сетке по-прежнему читает
products.title и products.image_url — форма продавца проставляет их из первой
вариации, потому что в ней первая вариация и есть сам товар.

Revision ID: x8f9a0b1c2d3
Revises: w7e8f9a0b1c2
Create Date: 2026-08-30 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'x8f9a0b1c2d3'
down_revision = 'w7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_variants", sa.Column("title", sa.String(256), nullable=True))
    op.add_column("product_variants", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("product_variants", "description")
    op.drop_column("product_variants", "title")
