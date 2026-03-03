"""Add team_seasons table for team-specific season tracking

Revision ID: 017
Revises: 016
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'team_seasons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'season', name='uq_team_season'),
    )
    op.create_index(op.f('ix_team_seasons_team_id'), 'team_seasons', ['team_id'], unique=False)
    op.create_index(op.f('ix_team_seasons_season'), 'team_seasons', ['season'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_team_seasons_season'), table_name='team_seasons')
    op.drop_index(op.f('ix_team_seasons_team_id'), table_name='team_seasons')
    op.drop_table('team_seasons')
