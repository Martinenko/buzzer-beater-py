"""Add NT match boxscore tables

Revision ID: 020
Revises: 019
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nt_match_boxscore",
        sa.Column("match_id", sa.Integer(), primary_key=True),
        sa.Column("retrieved_at", sa.DateTime(), nullable=True),
        sa.Column("match_type", sa.String(32), nullable=True),
        sa.Column("neutral", sa.Boolean(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("effort_delta", sa.Integer(), nullable=True),
        sa.Column("attendance_bleachers", sa.Integer(), nullable=True),
        sa.Column("attendance_lower_tier", sa.Integer(), nullable=True),
        sa.Column("attendance_courtside", sa.Integer(), nullable=True),
        sa.Column("attendance_luxury", sa.Integer(), nullable=True),
    )

    op.create_table(
        "nt_match_team_boxscore",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("nt_match_boxscore.match_id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_home", sa.Boolean(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("team_name", sa.String(100), nullable=True),
        sa.Column("short_name", sa.String(16), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("partial_q1", sa.Integer(), nullable=True),
        sa.Column("partial_q2", sa.Integer(), nullable=True),
        sa.Column("partial_q3", sa.Integer(), nullable=True),
        sa.Column("partial_q4", sa.Integer(), nullable=True),
        sa.Column("off_strategy", sa.String(32), nullable=True),
        sa.Column("def_strategy", sa.String(32), nullable=True),
        sa.Column("effort", sa.String(32), nullable=True),
        sa.Column("ratings_outside_scoring", sa.Float(), nullable=True),
        sa.Column("ratings_inside_scoring", sa.Float(), nullable=True),
        sa.Column("ratings_outside_defense", sa.Float(), nullable=True),
        sa.Column("ratings_inside_defense", sa.Float(), nullable=True),
        sa.Column("ratings_rebounding", sa.Float(), nullable=True),
        sa.Column("ratings_offensive_flow", sa.Float(), nullable=True),
        sa.Column("efficiency_pg", sa.Float(), nullable=True),
        sa.Column("efficiency_sg", sa.Float(), nullable=True),
        sa.Column("efficiency_sf", sa.Float(), nullable=True),
        sa.Column("efficiency_pf", sa.Float(), nullable=True),
        sa.Column("efficiency_c", sa.Float(), nullable=True),
        sa.Column("gdp_focus", sa.String(32), nullable=True),
        sa.Column("gdp_pace", sa.String(32), nullable=True),
        sa.Column("gdp_focus_hit", sa.Boolean(), nullable=True),
        sa.Column("gdp_pace_hit", sa.Boolean(), nullable=True),
        sa.Column("totals_fgm", sa.Integer(), nullable=True),
        sa.Column("totals_fga", sa.Integer(), nullable=True),
        sa.Column("totals_tpm", sa.Integer(), nullable=True),
        sa.Column("totals_tpa", sa.Integer(), nullable=True),
        sa.Column("totals_ftm", sa.Integer(), nullable=True),
        sa.Column("totals_fta", sa.Integer(), nullable=True),
        sa.Column("totals_oreb", sa.Integer(), nullable=True),
        sa.Column("totals_reb", sa.Integer(), nullable=True),
        sa.Column("totals_ast", sa.Integer(), nullable=True),
        sa.Column("totals_to", sa.Integer(), nullable=True),
        sa.Column("totals_stl", sa.Integer(), nullable=True),
        sa.Column("totals_blk", sa.Integer(), nullable=True),
        sa.Column("totals_pf", sa.Integer(), nullable=True),
        sa.Column("totals_pts", sa.Integer(), nullable=True),
    )
    op.create_index("ix_nt_match_team_boxscore_match_id", "nt_match_team_boxscore", ["match_id"])

    op.create_table(
        "nt_match_player_boxscore",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("nt_match_boxscore.match_id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("is_starter", sa.Boolean(), nullable=True),
        sa.Column("minutes_pg", sa.Integer(), nullable=True),
        sa.Column("minutes_sg", sa.Integer(), nullable=True),
        sa.Column("minutes_sf", sa.Integer(), nullable=True),
        sa.Column("minutes_pf", sa.Integer(), nullable=True),
        sa.Column("minutes_c", sa.Integer(), nullable=True),
        sa.Column("fgm", sa.Integer(), nullable=True),
        sa.Column("fga", sa.Integer(), nullable=True),
        sa.Column("tpm", sa.Integer(), nullable=True),
        sa.Column("tpa", sa.Integer(), nullable=True),
        sa.Column("ftm", sa.Integer(), nullable=True),
        sa.Column("fta", sa.Integer(), nullable=True),
        sa.Column("oreb", sa.Integer(), nullable=True),
        sa.Column("reb", sa.Integer(), nullable=True),
        sa.Column("ast", sa.Integer(), nullable=True),
        sa.Column("to", sa.Integer(), nullable=True),
        sa.Column("stl", sa.Integer(), nullable=True),
        sa.Column("blk", sa.Integer(), nullable=True),
        sa.Column("pf", sa.Integer(), nullable=True),
        sa.Column("pts", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
    )
    op.create_index("ix_nt_match_player_boxscore_match_id", "nt_match_player_boxscore", ["match_id"])
    op.create_index("ix_nt_match_player_boxscore_player_id", "nt_match_player_boxscore", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_nt_match_player_boxscore_player_id", table_name="nt_match_player_boxscore")
    op.drop_index("ix_nt_match_player_boxscore_match_id", table_name="nt_match_player_boxscore")
    op.drop_table("nt_match_player_boxscore")
    op.drop_index("ix_nt_match_team_boxscore_match_id", table_name="nt_match_team_boxscore")
    op.drop_table("nt_match_team_boxscore")
    op.drop_table("nt_match_boxscore")
