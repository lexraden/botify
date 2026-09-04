"""Модерация отзывов: product_reviews.status и moderated_at

Отзывы с оценкой >= review_auto_publish_min (4) публикуются сразу, низкие
(<= 3) ждут одобрения продавца во вкладке «Отзывы»; правка оценки
пересчитывает статус по тому же порогу, а через review_moderation_days (7)
неотмодерированное публикуется само — молчание продавца не прячет отзыв
навсегда.

Бэкфилл не нужен: существующие отзывы видны покупателям с самого запуска,
все они получают server_default='published' прямо при добавлении колонки.
Сам дефолт после этого снимается — значение всегда пишет модель.

Revision ID: r3c4d5e6f7g8
Revises: q2b3c4d5e6f7
Create Date: 2026-08-28 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'r3c4d5e6f7g8'
down_revision = 'q2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'product_reviews',
        sa.Column('status', sa.String(16), nullable=False, server_default='published'),
    )
    op.add_column(
        'product_reviews',
        sa.Column('moderated_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Дефолт был нужен только для бэкфилда существующих строк. batch-режим
    # на Postgres просто выполняет обычный ALTER TABLE, на SQLite — свой путь.
    with op.batch_alter_table('product_reviews') as batch:
        batch.alter_column('status', existing_type=sa.String(16), server_default=None)


def downgrade() -> None:
    op.drop_column('product_reviews', 'moderated_at')
    op.drop_column('product_reviews', 'status')
