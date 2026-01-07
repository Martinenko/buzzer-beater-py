"""Add auto_sync_enabled to users table

Revision ID: 002
Revises: 001
Create Date: 2026-01-07
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('auto_sync_enabled', sa.Boolean(), nullable=True, default=False))


def downgrade():
    op.drop_column('users', 'auto_sync_enabled')