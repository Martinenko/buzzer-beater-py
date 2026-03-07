"""Drop permanent NT flags from player

Revision ID: 022
Revises: 021
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("player", "last_nt_match_week")
    op.drop_column("player", "last_nt_match_year")
    op.drop_column("player", "is_nt_player")


def downgrade() -> None:
    op.add_column("player", sa.Column("is_nt_player", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("player", sa.Column("last_nt_match_year", sa.Integer(), nullable=True))
    op.add_column("player", sa.Column("last_nt_match_week", sa.Integer(), nullable=True))
