"""Add my team strategies to schedule_match

Revision ID: 014
Revises: 013
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schedule_match', sa.Column('my_off_strategy', sa.String(length=32), nullable=True))
    op.add_column('schedule_match', sa.Column('my_def_strategy', sa.String(length=32), nullable=True))
    op.add_column('schedule_match', sa.Column('my_effort', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('schedule_match', 'my_effort')
    op.drop_column('schedule_match', 'my_def_strategy')
    op.drop_column('schedule_match', 'my_off_strategy')
