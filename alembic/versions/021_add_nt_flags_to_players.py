"""Add NT flags to players and snapshots

Revision ID: 021
Revises: 020
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "player",
        sa.Column("is_nt_player", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("player", sa.Column("last_nt_match_year", sa.Integer(), nullable=True))
    op.add_column("player", sa.Column("last_nt_match_week", sa.Integer(), nullable=True))

    op.add_column(
        "player_snapshot",
        sa.Column("played_nt_match", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("player_snapshot", "played_nt_match")
    op.drop_column("player", "last_nt_match_week")
    op.drop_column("player", "last_nt_match_year")
    op.drop_column("player", "is_nt_player")
