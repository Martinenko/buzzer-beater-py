"""Widen bb_key column to accommodate Fernet-encrypted values.

Revision ID: 008
Revises: 007
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "bb_key",
        existing_type=sa.String(255),
        type_=sa.String(512),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "bb_key",
        existing_type=sa.String(512),
        type_=sa.String(255),
        existing_nullable=True,
    )
