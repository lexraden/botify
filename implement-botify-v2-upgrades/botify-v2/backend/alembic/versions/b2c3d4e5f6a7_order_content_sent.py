"""Отметка «подтверждение оплаты доехало до покупателя»

Заказ помечается оплаченным одним коммитом, а сообщение с материалами уходит
после него. Если процесс умрёт между этими шагами, ретрай вебхука упрётся в
гард статуса («уже обработан») и вернёт False — покупатель не получит купленное
никогда, а заказ будет числиться доставленным.

Колонка разводит два разных факта: «деньги приняты» (paid_at) и «человек
получил» (content_sent_at). NULL у оплаченного заказа — работа не доделана,
её добивает джоб resend_undelivered.

Бэкфилл обязателен и делает ровно обратное тому, что кажется: всем уже
оплаченным заказам проставляется content_sent_at = paid_at. Без этого первый
же проход джоба разослал бы подтверждения по всей истории заказов.

Revision ID: b2c3d4e5f6a7
Revises: z0b1c2d3e4f5
Create Date: 2026-08-31 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'z0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders", sa.Column("content_sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Всё, что уже оплачено, считаем доставленным: эти сообщения ушли до того,
    # как отметка появилась, и рассылать их заново нельзя
    op.execute("UPDATE orders SET content_sent_at = paid_at WHERE paid_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column("orders", "content_sent_at")
