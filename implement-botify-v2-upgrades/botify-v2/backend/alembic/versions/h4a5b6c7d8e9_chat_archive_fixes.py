"""chat_messages_archive.archived_at DEFAULT now() + индекс order_chats.status

Две правки по итогам ревью чата заказов.

1. `archived_at` создавался как NOT NULL без DEFAULT, хотя модель объявляет
   `server_default=func.now()`. SQLAlchemy при server_default значение в INSERT
   не отправляет — джоб архивации (раз в минуту) упал бы на первой же строке
   с NOT NULL. В тестах не видно: там схема поднимается через `create_all`,
   где дефолт есть. Проверено на мигрированной базе: INSERT без archived_at
   отбивается «null value in column "archived_at"».

2. Джобы обслуживания чатов (`lock_expired_chats`, `archive_old_chats`) ходят
   по `order_chats.status` каждую минуту. Без индекса это seq scan всей
   таблицы чатов — растёт вместе с числом заказов.

Revision ID: h4a5b6c7d8e9
Revises: g2b3c4d5e6f7
Create Date: 2026-08-26 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'h4a5b6c7d8e9'
down_revision = 'g2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'chat_messages_archive',
        'archived_at',
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=sa.text('now()'),
    )
    op.create_index(op.f('ix_order_chats_status'), 'order_chats', ['status'])


def downgrade() -> None:
    op.drop_index(op.f('ix_order_chats_status'), table_name='order_chats')
    op.alter_column(
        'chat_messages_archive',
        'archived_at',
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=None,
    )
