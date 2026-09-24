"""user language

Revision ID: 0003_user_language
Revises: 0002_deadlines
Create Date: 2026-09-24 15:19:06.397860
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003_user_language'
down_revision: str | None = '0002_deadlines'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('language', sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'language')
