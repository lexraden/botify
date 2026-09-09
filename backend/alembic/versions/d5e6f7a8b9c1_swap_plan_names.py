"""Названия платных тарифов поменялись местами: Plus — младший, Pro — старший

Решение владельца от 2026-09-09: «Pro» звучит сильнее «Plus», поэтому старший
тариф (безлимит + оплата по реквизитам в чате) теперь называется Pro, а
младший (только безлимит) — Plus. Цены остались за функциями, а не за
названиями: 20 USDT за младший, 50 за старший.

Тариф хранится строкой в sellers.plan, поэтому переименование — это правка
данных, а не только словарей. Swap делается через временное значение: прямой
UPDATE ... 'pro'->'plus' сначала перевёл бы всех старших в младшие, а вторым
запросом вернул бы их обратно вместе с настоящими младшими.

downgrade — тот же swap: операция сама себе обратная.

Revision ID: d5e6f7a8b9c1
Revises: b3c4d5e6f7a8
Create Date: 2026-09-09 12:00:00.000000

"""
from alembic import op


revision = 'd5e6f7a8b9c1'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def _swap() -> None:
    op.execute("UPDATE sellers SET plan = 'plan_swap_tmp' WHERE plan = 'pro'")
    op.execute("UPDATE sellers SET plan = 'pro' WHERE plan = 'plus'")
    op.execute("UPDATE sellers SET plan = 'plus' WHERE plan = 'plan_swap_tmp'")


def upgrade() -> None:
    _swap()


def downgrade() -> None:
    _swap()
