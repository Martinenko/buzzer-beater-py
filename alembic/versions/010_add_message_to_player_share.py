"""Add message field to player_share table

Revision ID: 010
Revises: 009
Create Date: 2026-02-13

"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_share", sa.Column("message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("player_share", "message")
