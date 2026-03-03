"""
One-time script to reset boxscore_fetched flag for matches that need re-fetching.
This ensures all matches will be re-fetched to get complete GDP data.
Run this once manually: python scripts/reset_boxscore_fetched.py
"""
import asyncio
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import async_session

async def reset_boxscore_fetched():
    """Reset boxscore_fetched flag for matches with missing prediction data"""
    async with async_session() as session:
        # Reset boxscore_fetched for matches that have scores but missing prediction hit data
        result = await session.execute(text("""
            UPDATE schedule_match 
            SET boxscore_fetched = FALSE
            WHERE home_score IS NOT NULL 
              AND away_score IS NOT NULL
              AND (predicted_focus_hit IS NULL OR opponent_focus_hit IS NULL)
        """))
        
        await session.commit()
        
        print(f"Reset {result.rowcount} matches for boxscore re-fetch")
        print("Done!")

if __name__ == "__main__":
    try:
        asyncio.run(reset_boxscore_fetched())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
