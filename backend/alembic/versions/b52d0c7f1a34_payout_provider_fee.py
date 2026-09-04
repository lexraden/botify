"""payout provider fee

Комиссия Crypto Pay за приём платежа удерживается сервисом с поступления,
поэтому она вычитается из доли продавца, а не из комиссии платформы.

Revision ID: b52d0c7f1a34
Revises: 7c41ab90ef21
Create Date: 2026-08-21 12:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b52d0c7f1a34'
down_revision = '7c41ab90ef21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'payouts',
        sa.Column(
            'provider_fee',
            sa.Numeric(precision=18, scale=6),
            nullable=False,
            server_default='0',
        ),
    )
    # Старые выплаты считались без учёта комиссии сервиса — оставляем их как
    # есть (деньги по ним уже посчитаны), нулевое значение это и означает.


def downgrade() -> None:
    op.drop_column('payouts', 'provider_fee')
