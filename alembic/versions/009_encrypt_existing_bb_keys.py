"""Encrypt existing plain-text bb_key values in the users table.

Revision ID: 009
Revises: 008
Create Date: 2026-02-10
"""
import os

from alembic import op
from cryptography.fernet import Fernet
from sqlalchemy import text

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def _encrypt(value: str, fernet: Fernet) -> str:
    return fernet.encrypt(value.encode()).decode()


def _decrypt(value: str, fernet: Fernet) -> str:
    return fernet.decrypt(value.encode()).decode()


def upgrade() -> None:
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    if not encryption_key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is required")

    fernet = Fernet(encryption_key.encode())
    conn = op.get_bind()

    rows = conn.execute(
        text("SELECT id, bb_key FROM users WHERE bb_key IS NOT NULL")
    ).fetchall()

    for user_id, bb_key in rows:
        # Skip already-encrypted values (Fernet tokens start with gAAAAA)
        if bb_key.startswith("gAAAAA"):
            continue

        encrypted_key = _encrypt(bb_key, fernet)
        conn.execute(
            text("UPDATE users SET bb_key = :key WHERE id = :id"),
            {"key": encrypted_key, "id": user_id},
        )


def downgrade() -> None:
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    if not encryption_key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is required")

    fernet = Fernet(encryption_key.encode())
    conn = op.get_bind()

    rows = conn.execute(
        text("SELECT id, bb_key FROM users WHERE bb_key IS NOT NULL")
    ).fetchall()

    for user_id, bb_key in rows:
        if not bb_key.startswith("gAAAAA"):
            continue

        decrypted_key = _decrypt(bb_key, fernet)
        conn.execute(
            text("UPDATE users SET bb_key = :key WHERE id = :id"),
            {"key": decrypted_key, "id": user_id},
        )