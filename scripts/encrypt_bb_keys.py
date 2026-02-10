"""One-time script to encrypt existing plain-text bb_key values in the users table.

Usage:
    cd buzzer-beater-py
    python -m scripts.encrypt_bb_keys
"""
import asyncio

from sqlalchemy import text

from app.database import async_session
from app.utils.crypto import encrypt


async def main():
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, bb_key FROM users WHERE bb_key IS NOT NULL")
        )
        rows = result.fetchall()

        if not rows:
            print("No users with bb_key found.")
            return

        encrypted = 0
        skipped = 0

        for user_id, bb_key in rows:
            # Fernet tokens start with gAAAAA — skip already-encrypted values
            if bb_key.startswith("gAAAAA"):
                skipped += 1
                continue

            encrypted_key = encrypt(bb_key)
            await session.execute(
                text("UPDATE users SET bb_key = :key WHERE id = :id"),
                {"key": encrypted_key, "id": user_id},
            )
            encrypted += 1

        await session.commit()
        print(f"Done. Encrypted: {encrypted}, Skipped (already encrypted): {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
