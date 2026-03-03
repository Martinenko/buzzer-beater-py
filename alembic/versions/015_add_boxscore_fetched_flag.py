"""Add boxscore_fetched flag to schedule_match

Revision ID: 015
Revises: 014
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schedule_match', sa.Column('boxscore_fetched', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('schedule_match', 'boxscore_fetched')
