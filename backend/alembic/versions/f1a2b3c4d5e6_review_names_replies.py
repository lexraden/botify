"""Отзывы: псевдоним автора и ответ продавца

product_reviews получает author_name (случайный псевдоним вместо личности —
сервис анонимный, но совсем безымянные отзывы читаются плохо), а также
reply_body/reply_at — один ответ продавца на отзыв. Существующим отзывам
псевдонимы проставляются бэкфиллом; генератор инлайновый, чтобы миграция
не зависела от живого кода приложения.

Revision ID: f1a2b3c4d5e6
Revises: e9f0a1b2c3d4
Create Date: 2026-08-25 22:00:00.000000

"""
import secrets

from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e6'
down_revision = 'e9f0a1b2c3d4'
branch_labels = None
depends_on = None

# те же имена, что в app/services/reviews.py; продублированы сознательно
_NAMES = [
    "Александр", "Алексей", "Анатолий", "Андрей", "Анна", "Артём", "Борис",
    "Валерия", "Василий", "Вера", "Виктория", "Владимир", "Глеб", "Дарья",
    "Дмитрий", "Егор", "Екатерина", "Елена", "Иван", "Игорь", "Илья",
    "Кирилл", "Ксения", "Лев", "Мария", "Максим", "Михаил", "Никита",
    "Николай", "Ольга", "Павел", "Полина", "Роман", "Светлана", "Сергей",
    "Татьяна", "Фёдор", "Юлия", "Юрий", "Яна",
]
_INITIALS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ"


def _random_name() -> str:
    return f"{secrets.choice(_NAMES)} {secrets.choice(_INITIALS)}."


def upgrade() -> None:
    op.add_column('product_reviews', sa.Column('author_name', sa.String(length=64), nullable=True))
    op.add_column('product_reviews', sa.Column('reply_body', sa.Text(), nullable=True))
    op.add_column(
        'product_reviews',
        sa.Column('reply_at', sa.DateTime(timezone=True), nullable=True),
    )

    # у старых отзывов псевдонима нет — выдаём каждому случайный
    conn = op.get_bind()
    ids = conn.execute(
        sa.text("SELECT id FROM product_reviews WHERE author_name IS NULL")
    ).fetchall()
    for (review_id,) in ids:
        conn.execute(
            sa.text("UPDATE product_reviews SET author_name = :n WHERE id = :i"),
            {"n": _random_name(), "i": review_id},
        )


def downgrade() -> None:
    op.drop_column('product_reviews', 'reply_at')
    op.drop_column('product_reviews', 'reply_body')
    op.drop_column('product_reviews', 'author_name')
