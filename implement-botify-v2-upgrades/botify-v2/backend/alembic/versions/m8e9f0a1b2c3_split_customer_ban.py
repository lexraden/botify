"""customers.mailing_blocked — рассылка и бан перестают быть одним флагом

`is_banned` делал две разные работы. Рассылка ставила его на
TelegramForbiddenError — то есть на «покупатель заблокировал бота или удалил
чат», а `get_buyer` по этому же флагу закрывал весь Mini App с 403. Человек
глушил бота, чтобы не получать рассылки, и терял вместе с этим свои
оплаченные заказы, историю и переписку с продавцом. Снять флаг не мог никто:
в коде не было ни одной строки, возвращающей его в False.

Теперь «не доставляется» и «доступ закрыт» — разные вещи:
- `mailing_blocked` ставит рассылка; он влияет только на рассылки;
- `is_banned` остаётся под настоящий бан и доступ закрывает по-прежнему.

Бэкфилл переносит текущие значения в новый флаг и снимает `is_banned`:
все существующие «баны» на самом деле проставлены рассылкой, других
источников у флага не было.

Revision ID: m8e9f0a1b2c3
Revises: k7d8e9f0a1b2
Create Date: 2026-08-26 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'm8e9f0a1b2c3'
down_revision = 'k7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'customers',
        sa.Column(
            'mailing_blocked',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    # всё, что помечено сейчас, поставлено рассылкой — переносим по смыслу
    op.execute("UPDATE customers SET mailing_blocked = is_banned WHERE is_banned")
    op.execute("UPDATE customers SET is_banned = false")


def downgrade() -> None:
    # возвращаем прежнее слипшееся значение, чтобы старый код вёл себя как раньше
    op.execute("UPDATE customers SET is_banned = true WHERE mailing_blocked")
    op.drop_column('customers', 'mailing_blocked')
