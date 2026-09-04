"""orders.reminded_at + mailings.heartbeat_at — для фоновых задач обслуживания

Две колонки под задачи обслуживания:

- `orders.reminded_at` — когда продавцу ушло напоминание о заказе, который
  оплачен, но не отправлен. Без отметки джоб слал бы напоминание на каждом
  тике.
- `mailings.heartbeat_at` — признак жизни идущей рассылки: ставится на старте
  и обновляется по ходу отправки. Без него нельзя отличить рассылку, которая
  идёт прямо сейчас, от застрявшей навсегда после падения процесса — статус
  `sending` у них общий. Именно признак жизни, а не момент старта: рассылка по
  большой базе идёт дольше любого разумного порога, и по одной лишь метке
  старта её «оживили» бы прямо на ходу.

Обе nullable и без бэкфилла: у существующих строк «напоминание не слали» и
«признака жизни нет» — ровно то, что означает NULL. Рассылки с
`heartbeat_at IS NULL` оцениваются по `created_at` (см. app/services/mailing.py).

Revision ID: j6c7d8e9f0a1
Revises: i5b6c7d8e9f0
Create Date: 2026-08-26 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'j6c7d8e9f0a1'
down_revision = 'i5b6c7d8e9f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mailings', sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('mailings', 'heartbeat_at')
    op.drop_column('orders', 'reminded_at')
