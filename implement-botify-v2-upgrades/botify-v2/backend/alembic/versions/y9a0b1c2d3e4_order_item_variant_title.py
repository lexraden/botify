"""Снимок названия вариации в строке заказа

У вариации появилось своё название (`x8f9a0b1c2d3`), а товарное — это имя
первой из них: его проставляет форма продавца. Значит строка заказа, собранная
из товарного названия, для второй вариации называла бы чужой вариант — человек
купил «Футболку синюю», а в чеке видел «Футболку красную».

Снимаем по той же причине, по которой рядом уже снимаются цена и подпись
(`variant_label`): продавец переименует вариацию или уберёт её из товара, а в
старом заказе должно остаться то, за что человек заплатил.

Колонка nullable и без бэкфилла: NULL значит «брать товарное», и у всех
существующих строк поведение остаётся ровно прежним.

Revision ID: y9a0b1c2d3e4
Revises: x8f9a0b1c2d3
Create Date: 2026-08-30 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'y9a0b1c2d3e4'
down_revision = 'x8f9a0b1c2d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("variant_title", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "variant_title")
