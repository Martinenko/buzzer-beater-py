"""Add schedule matches

Revision ID: 013
Revises: 012
Create Date: 2026-02-23

"""
from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_match",
        sa.Column("match_id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(length=32), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(), nullable=True),
        sa.Column("home_team_id", sa.Integer(), nullable=True),
        sa.Column("home_team_name", sa.String(length=100), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_team_id", sa.Integer(), nullable=True),
        sa.Column("away_team_name", sa.String(length=100), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("opponent_team_id", sa.Integer(), nullable=True),
        sa.Column("opponent_team_name", sa.String(length=100), nullable=True),
        sa.Column("opponent_focus", sa.String(length=32), nullable=True),
        sa.Column("opponent_pace", sa.String(length=32), nullable=True),
        sa.Column("opponent_focus_hit", sa.Boolean(), nullable=True),
        sa.Column("opponent_pace_hit", sa.Boolean(), nullable=True),
        sa.Column("opponent_off_strategy", sa.String(length=32), nullable=True),
        sa.Column("opponent_def_strategy", sa.String(length=32), nullable=True),
        sa.Column("opponent_effort", sa.String(length=32), nullable=True),
        sa.Column("predicted_focus", sa.String(length=32), nullable=True),
        sa.Column("predicted_pace", sa.String(length=32), nullable=True),
        sa.Column("predicted_focus_hit", sa.Boolean(), nullable=True),
        sa.Column("predicted_pace_hit", sa.Boolean(), nullable=True),
        sa.Column("details_retrieved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_schedule_match_team_id", "schedule_match", ["team_id"])
    op.create_index("ix_schedule_match_season", "schedule_match", ["season"])


def downgrade() -> None:
    op.drop_index("ix_schedule_match_season", table_name="schedule_match")
    op.drop_index("ix_schedule_match_team_id", table_name="schedule_match")
    op.drop_table("schedule_match")
