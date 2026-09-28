"""currency

Revision ID: 0010_currency
Revises: 0009_rs_banks
Create Date: 2026-09-28 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0010_currency'
down_revision: str | None = '0009_rs_banks'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('exchange_rate', sa.Numeric(precision=14, scale=6), nullable=True))
    op.add_column('transactions', sa.Column('rate_date', sa.Date(), nullable=True))
    op.add_column('transactions', sa.Column('gel_amount', sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column('transactions', sa.Column('gel_vat_amount', sa.Numeric(precision=14, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('transactions', 'gel_vat_amount')
    op.drop_column('transactions', 'gel_amount')
    op.drop_column('transactions', 'rate_date')
    op.drop_column('transactions', 'exchange_rate')
