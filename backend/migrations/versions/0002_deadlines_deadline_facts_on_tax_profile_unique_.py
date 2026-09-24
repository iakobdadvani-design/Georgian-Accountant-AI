"""deadline facts on tax profile, unique tax events

Revision ID: 0002_deadlines
Revises: 0001_baseline
Create Date: 2026-09-24 14:38:32.411313
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002_deadlines'
down_revision: str | None = '0001_baseline'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('company_tax_profiles', sa.Column('has_employees', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('company_tax_profiles', sa.Column('owns_property', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_unique_constraint('uq_tax_events_company_rule_period', 'tax_events', ['company_id', 'rule_id', 'period_start'])


def downgrade() -> None:
    op.drop_constraint('uq_tax_events_company_rule_period', 'tax_events', type_='unique')
    op.drop_column('company_tax_profiles', 'owns_property')
    op.drop_column('company_tax_profiles', 'has_employees')
