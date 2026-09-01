"""Платежи за Pro-подписку продавца

Подписка живёт двумя полями продавца (plan, pro_expires_at), а эта таблица —
журнал оплат: идемпотентность вебхуков, учёт выручки платформы и ответ на
вопрос «за что списали».

Уникальность invoice_id и telegram_charge_id — не украшение, а сам механизм
идемпотентности: Crypto Pay ретраит вебхук, Telegram может доставить
successful_payment повторно, и вторая вставка обязана упасть, а не продлить
подписку второй раз за те же деньги.

Revision ID: z0b1c2d3e4f5
Revises: y9a0b1c2d3e4
Create Date: 2026-08-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'z0b1c2d3e4f5'
down_revision = 'y9a0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("amount_usdt", sa.Numeric(18, 6), nullable=True),
        sa.Column("amount_stars", sa.Integer(), nullable=True),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_charge_id", sa.String(128), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("invoice_id", name="uq_subscription_invoice"),
        sa.UniqueConstraint("telegram_charge_id", name="uq_subscription_charge"),
    )
    op.create_index("ix_subscription_payments_seller_id", "subscription_payments", ["seller_id"])
    # метка «о каком окончании подписки уже напомнили»: без неё напоминание
    # уходило бы каждые десять минут все последние дни подписки
    op.add_column(
        "sellers", sa.Column("pro_reminded_for", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sellers", "pro_reminded_for")
    op.drop_index("ix_subscription_payments_seller_id", table_name="subscription_payments")
    op.drop_table("subscription_payments")
