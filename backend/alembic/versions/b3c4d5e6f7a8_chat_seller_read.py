"""Отметка прочтения переписки продавцом

Списка диалогов у продавца не было вовсе — в чат он попадал только из строки
заказа. Вместе со списком нужен признак «есть новые», иначе инбокс не отвечает
на единственный вопрос, ради которого его открывают.

Хранится временем, а не флагом: флаг пришлось бы сбрасывать при каждом новом
сообщении покупателя, а время само отвечает и на «сколько новых», и на «есть
ли новые» — сравнением с created_at сообщений.

Бэкфилл не нужен: NULL означает «не открывал», то есть вся переписка
покупателя считается непрочитанной. Для существующих чатов это и есть правда —
продавец их в списке ещё не видел.

Revision ID: b3c4d5e6f7a8
Revises: c3d4e5f6a7b8
Create Date: 2026-09-01 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c4d5e6f7a8'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_chats", sa.Column("seller_read_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("order_chats", "seller_read_at")
