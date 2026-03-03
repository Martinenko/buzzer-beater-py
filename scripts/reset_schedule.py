import argparse
import asyncio

from sqlalchemy import text, bindparam
from sqlalchemy.exc import SQLAlchemyError

from app.database import async_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset schedule + boxscore data for a team")
    parser.add_argument("--team-id", type=int, required=True, help="BB team id to reset")
    return parser.parse_args()


async def reset_schedule(team_id: int) -> None:
    async with async_session() as db:
        match_ids_result = await db.execute(
            text("SELECT match_id FROM schedule_match WHERE team_id = :team_id"),
            {"team_id": team_id}
        )
        match_ids = [row[0] for row in match_ids_result.all()]

        if match_ids:
            for delete_sql in [
                "DELETE FROM match_player_boxscore WHERE match_id IN :match_ids",
                "DELETE FROM match_team_boxscore WHERE match_id IN :match_ids",
                "DELETE FROM match_boxscore WHERE match_id IN :match_ids",
            ]:
                try:
                    await db.execute(
                        text(delete_sql).bindparams(bindparam("match_ids", expanding=True)),
                        {"match_ids": match_ids}
                    )
                except SQLAlchemyError:
                    pass

        await db.execute(
            text("DELETE FROM schedule_match WHERE team_id = :team_id"),
            {"team_id": team_id}
        )
        await db.commit()

        print(f"Deleted schedule for team_id={team_id}. Matches removed: {len(match_ids)}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(reset_schedule(args.team_id))
