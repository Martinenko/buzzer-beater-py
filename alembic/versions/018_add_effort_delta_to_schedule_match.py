"""Add effort_delta column to schedule_match

Revision ID: 018
Revises: 017
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedule_match", sa.Column("effort_delta", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedule_match", "effort_delta")
