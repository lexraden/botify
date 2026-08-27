"""Ручной выбор языка покупателя для уведомлений

Пуши покупателю («заказ оплачен», «продавец отправил заказ») раньше были только
русскими. Теперь язык уведомлений — как в Mini App: ручной выбор в профиле
главнее, без него русский идёт тем, у кого Telegram настроен на русский,
всем остальным — английский.

Колонка `customers.locale` хранит именно ручной выбор ('ru'/'en') и NULL,
пока человек язык не менял: автоматический детект по language_code считается
на лету, чтобы смена языка в Telegram-профиле подхватывалась без записи.

Revision ID: p1a2b3c4d5e6
Revises: n9d0e1f2a3b4
Create Date: 2026-08-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'p1a2b3c4d5e6'
down_revision = 'n9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'customers',
        sa.Column('locale', sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('customers', 'locale')
