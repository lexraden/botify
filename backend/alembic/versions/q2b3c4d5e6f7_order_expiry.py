"""Неоплаченные заказы истекают: orders.expires_at

До сих пор заказ в pending_payment жил вечно: отменить его мог только сам
покупатель, а брошенная корзина оставалась в «Моих покупках» навсегда. Счёт в
Crypto Pay при этом протухает через час — согласуем заказ с этим сроком.

expires_at ставится при создании заказа и продлевается при каждой новой
ссылке на оплату (POST /orders/{id}/pay выписывает новый часовой счёт —
заказу даётся столько же). Джоб в maintenance_loop отменяет просроченные.

Бэкфилл: существующим pending_payment ставим created_at + 1 час, то есть
первым же проходом джоба все давно брошенные корзины отменятся. Это желаемый
эффект, но о нём нужно сказать вслух при деплое.

Revision ID: q2b3c4d5e6f7
Revises: p1a2b3c4d5e6
Create Date: 2026-08-28 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'q2b3c4d5e6f7'
down_revision = 'p1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'orders', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True)
    )
    # Бэкфилл только для неоплаченных: оплаченные и отменённые не истекают.
    # Postgres — основной диалект; ветка SQLite — чтобы миграцию можно было
    # прогнать в обе стороны локально (см. CLAUDE.md).
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "UPDATE orders SET expires_at = datetime(created_at, '+1 hour') "
            "WHERE status = 'pending_payment'"
        )
    else:
        op.execute(
            "UPDATE orders SET expires_at = created_at + interval '1 hour' "
            "WHERE status = 'pending_payment'"
        )


def downgrade() -> None:
    op.drop_column('orders', 'expires_at')
