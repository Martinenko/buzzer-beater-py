"""Initial MySQL migration

Revision ID: 001
Revises:
Create Date: 2026-01-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('login_name', sa.String(100), nullable=False),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('bb_key', sa.String(255), nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('supporter', sa.Boolean(), nullable=True, default=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_login_name', 'users', ['login_name'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=False)

    # Team table
    op.create_table('team',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('short_name', sa.String(20), nullable=False),
        sa.Column('team_type', sa.Enum('MAIN', 'UTOPIA', name='teamtype'), nullable=False),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('league_id', sa.Integer(), nullable=True),
        sa.Column('league_name', sa.String(100), nullable=True),
        sa.Column('league_level', sa.Integer(), nullable=True),
        sa.Column('country_id', sa.Integer(), nullable=True),
        sa.Column('country_name', sa.String(50), nullable=True),
        sa.Column('rival_id', sa.Integer(), nullable=True),
        sa.Column('rival_name', sa.String(100), nullable=True),
        sa.Column('coach_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['coach_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_team_team_id', 'team', ['team_id'], unique=True)

    # Player table
    op.create_table('player',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('country', sa.String(50), nullable=False),
        sa.Column('team_name', sa.String(100), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('potential', sa.Integer(), nullable=False),
        sa.Column('game_shape', sa.Integer(), nullable=False),
        sa.Column('salary', sa.Integer(), nullable=True),
        sa.Column('dmi', sa.Integer(), nullable=True),
        sa.Column('best_position', sa.String(10), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
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
        sa.Column('current_team_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['current_team_id'], ['team.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_player_player_id', 'player', ['player_id'], unique=True)

    # Player share table
    op.create_table('player_share',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('player_id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('recipient_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['player_id'], ['player.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'recipient_id', name='unique_player_share')
    )


def downgrade() -> None:
    op.drop_table('player_share')
    op.drop_index('ix_player_player_id', table_name='player')
    op.drop_table('player')
    op.drop_index('ix_team_team_id', table_name='team')
    op.drop_table('team')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_login_name', table_name='users')
    op.drop_table('users')