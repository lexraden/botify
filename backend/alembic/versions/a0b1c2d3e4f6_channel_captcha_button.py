"""Заявка в канал одобряется после капчи; текст кнопки задаёт продавец

До этого «капча» была декоративной: бот сначала одобрял заявку и только потом
присылал кнопку «Я не робот» — человек оказывался в канале ещё до нажатия.
Теперь одобрение — по нажатию, а текст кнопки продавец может поменять
(по умолчанию «Я не робот 🤖» на языке покупателя).

Текст сообщения рядом с кнопкой — уже существующая channels.greeting_text,
которая до этой правки настраивалась, но никуда не отправлялась.

NULL — стандартная кнопка. Бэкфилл не нужен.

Revision ID: a0b1c2d3e4f6
Revises: f8a9b0c1d2e3
Create Date: 2026-10-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a0b1c2d3e4f6'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('channels', sa.Column('captcha_button', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('channels', 'captcha_button')
