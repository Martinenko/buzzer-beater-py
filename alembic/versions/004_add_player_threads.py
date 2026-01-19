"""Add player_thread and player_message tables

Revision ID: 004
Revises: 003
Create Date: 2025-01-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create player_thread table
    op.create_table(
        'player_thread',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('player_id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('participant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['player.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['participant_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'owner_id', 'participant_id', name='unique_player_thread'),
    )

    # Create indexes for faster queries
    op.create_index('ix_player_thread_player_id', 'player_thread', ['player_id'])
    op.create_index('ix_player_thread_owner_id', 'player_thread', ['owner_id'])
    op.create_index('ix_player_thread_participant_id', 'player_thread', ['participant_id'])

    # Create player_message table
    op.create_table(
        'player_message',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('thread_id', sa.Uuid(), nullable=False),
        sa.Column('sender_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['player_thread.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create index for faster message retrieval
    op.create_index('ix_player_message_thread_id', 'player_message', ['thread_id'])


def downgrade() -> None:
    op.drop_index('ix_player_message_thread_id')
    op.drop_table('player_message')
    op.drop_index('ix_player_thread_participant_id')
    op.drop_index('ix_player_thread_owner_id')
    op.drop_index('ix_player_thread_player_id')
    op.drop_table('player_thread')
