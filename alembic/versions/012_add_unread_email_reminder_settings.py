"""Add email reminder settings to users

Revision ID: 012
Revises: 011
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("users", sa.Column("unread_reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("users", sa.Column("unread_reminder_delay_min", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("users", sa.Column("last_unread_reminder_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_unread_reminder_sent_at")
    op.drop_column("users", "unread_reminder_delay_min")
    op.drop_column("users", "unread_reminder_enabled")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email")
