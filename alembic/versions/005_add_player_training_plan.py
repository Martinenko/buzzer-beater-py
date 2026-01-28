"""Add player_training_plan table

Revision ID: 005
Revises: 004
Create Date: 2025-01-19

"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_training_plan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("jump_shot", sa.Integer(), nullable=True),
        sa.Column("jump_range", sa.Integer(), nullable=True),
        sa.Column("outside_defense", sa.Integer(), nullable=True),
        sa.Column("handling", sa.Integer(), nullable=True),
        sa.Column("driving", sa.Integer(), nullable=True),
        sa.Column("passing", sa.Integer(), nullable=True),
        sa.Column("inside_shot", sa.Integer(), nullable=True),
        sa.Column("inside_defense", sa.Integer(), nullable=True),
        sa.Column("rebounding", sa.Integer(), nullable=True),
        sa.Column("shot_blocking", sa.Integer(), nullable=True),
        sa.Column("stamina", sa.Integer(), nullable=True),
        sa.Column("free_throws", sa.Integer(), nullable=True),
        sa.Column("experience", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", name="uq_player_training_plan_player_id"),
    )
    op.create_index("ix_player_training_plan_player_id", "player_training_plan", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_player_training_plan_player_id", table_name="player_training_plan")
    op.drop_table("player_training_plan")
