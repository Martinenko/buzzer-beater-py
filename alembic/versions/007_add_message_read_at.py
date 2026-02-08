"""Add read_at column to player_message for read tracking.

Revision ID: 007
Revises: 006
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_message", sa.Column("read_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("player_message", "read_at")
