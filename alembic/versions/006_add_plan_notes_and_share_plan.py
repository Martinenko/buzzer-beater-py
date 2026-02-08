"""Add notes to player_training_plan and share_plan to player_share

Revision ID: 006
Revises: 005
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_training_plan", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("player_share", sa.Column("share_plan", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("player_share", "share_plan")
    op.drop_column("player_training_plan", "notes")
