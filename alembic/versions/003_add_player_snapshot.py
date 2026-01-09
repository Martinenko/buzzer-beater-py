"""Add player_snapshot table

Revision ID: 003
Revises: 002
Create Date: 2025-01-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'player_snapshot',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('player_id', sa.Uuid(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('week_of_year', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('country', sa.String(50), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('potential', sa.Integer(), nullable=False),
        sa.Column('game_shape', sa.Integer(), nullable=False),
        sa.Column('salary', sa.Integer(), nullable=True),
        sa.Column('dmi', sa.Integer(), nullable=True),
        sa.Column('best_position', sa.String(10), nullable=True),
        sa.Column('jump_shot', sa.Integer(), nullable=True),
        sa.Column('jump_range', sa.Integer(), nullable=True),
        sa.Column('outside_defense', sa.Integer(), nullable=True),
        sa.Column('handling', sa.Integer(), nullable=True),
        sa.Column('driving', sa.Integer(), nullable=True),
        sa.Column('passing', sa.Integer(), nullable=True),
        sa.Column('inside_shot', sa.Integer(), nullable=True),
        sa.Column('inside_defense', sa.Integer(), nullable=True),
        sa.Column('rebounding', sa.Integer(), nullable=True),
        sa.Column('shot_blocking', sa.Integer(), nullable=True),
        sa.Column('stamina', sa.Integer(), nullable=True),
        sa.Column('free_throws', sa.Integer(), nullable=True),
        sa.Column('experience', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['player.id']),
        sa.ForeignKeyConstraint(['team_id'], ['team.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'year', 'week_of_year', name='uq_player_week'),
    )

    # Create index for faster queries by team and week
    op.create_index('ix_player_snapshot_team_week', 'player_snapshot', ['team_id', 'year', 'week_of_year'])


def downgrade() -> None:
    op.drop_index('ix_player_snapshot_team_week')
    op.drop_table('player_snapshot')