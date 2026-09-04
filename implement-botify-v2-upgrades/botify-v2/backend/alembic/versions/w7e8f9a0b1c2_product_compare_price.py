"""Зачёркнутая «старая» цена у товара без вариаций

Скидка появилась вместе с вариациями и осталась только на них
(`product_variants.compare_at_price`). Товар без вариаций — а это подавляющее
большинство каталога — показать скидку не мог вовсе: заводить ради одной
зачёркнутой цены набор вариаций бессмысленно.

Колонка nullable и без значения по умолчанию: NULL — скидки нет, ровно как у
вариаций. Существующие товары не трогаются.

У товара с вариациями это поле обнуляется при сохранении
(`app/services/variants.py:recompute_product_totals`): витринная цена там —
минимум по вариациям, и зачёркивать рядом с ней своё старое число было бы
враньём про размер скидки.

Revision ID: w7e8f9a0b1c2
Revises: v6d7e8f9a0b1
Create Date: 2026-08-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'w7e8f9a0b1c2'
down_revision = 'v6d7e8f9a0b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("compare_at_price", sa.Numeric(18, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "compare_at_price")
