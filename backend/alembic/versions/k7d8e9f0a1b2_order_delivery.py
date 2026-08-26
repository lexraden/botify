"""orders.delivery — куда везти физический заказ

Продавать физические товары было нельзя по-настоящему: в схеме не было ни
адреса, ни телефона, ни пункта выдачи, а продавцу заказ приходит без данных
покупателя («сервис анонимный»). Оставался только свободный `comment` — и
продавец шёл выяснять адрес в чат заказа с каждым покупателем.

Форма та же, что у `fulfillment`: JSONB рядом с ним, а не набор колонок —
состав полей ещё будет меняться (ПВЗ, страна, индекс), и каждый раз это была
бы миграция. Ключи: name, phone, address.

Заполняется только у заказов с физическими позициями; у цифровых остаётся NULL.
Бэкфилл невозможен и не нужен: у старых заказов этих данных просто не было.

Revision ID: k7d8e9f0a1b2
Revises: j6c7d8e9f0a1
Create Date: 2026-08-26 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'k7d8e9f0a1b2'
down_revision = 'j6c7d8e9f0a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'orders',
        sa.Column(
            'delivery',
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('orders', 'delivery')
