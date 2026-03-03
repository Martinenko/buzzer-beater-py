"""
One-time cleanup script to remove derived opponent predictions from database.
Run this once manually: python scripts/cleanup_derived_predictions.py
"""
import asyncio
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import async_session

async def cleanup_derived_predictions():
    """Remove opponent_focus and opponent_pace where hit values are NULL (derived, not real predictions)"""
    async with async_session() as session:
        # Clear opponent_focus where hit is NULL (derived)
        result1 = await session.execute(text("""
            UPDATE schedule_match 
            SET opponent_focus = NULL
            WHERE opponent_focus_hit IS NULL AND opponent_focus IS NOT NULL
        """))
        
        # Clear opponent_pace where hit is NULL (derived)
        result2 = await session.execute(text("""
            UPDATE schedule_match 
            SET opponent_pace = NULL
            WHERE opponent_pace_hit IS NULL AND opponent_pace IS NOT NULL
        """))
        
        await session.commit()
        
        print(f"Cleaned up {result1.rowcount} opponent_focus values")
        print(f"Cleaned up {result2.rowcount} opponent_pace values")
        print("Done!")

if __name__ == "__main__":
    try:
        asyncio.run(cleanup_derived_predictions())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
