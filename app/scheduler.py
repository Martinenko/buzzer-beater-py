"""
Scheduled tasks for automatic roster synchronization.
Runs every Friday at 1 PM CET (12:00 UTC in winter, 11:00 UTC in summer).
"""
import asyncio
import logging
from datetime import datetime
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.services.bb_api import BBApiClient

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_roster_for_team(user: User, team: Team, db: AsyncSession, http_client=None) -> int:
    """Sync roster for a single team. Returns number of players synced."""
    if not user.bb_key:
        logger.warning(f"User {user.username} has no BB key, skipping team {team.name}")
        return 0

    is_utopia = (team.team_type.value == "UTOPIA")

    try:
        bb_client = BBApiClient(user.bb_key)
        bb_players = await bb_client.get_roster_with_client(
            team.team_id,
            username=user.login_name,
            is_utopia=is_utopia,
            client=http_client
        )

        if not bb_players:
            logger.warning(f"No players returned for team {team.name} (ID: {team.team_id})")
            return 0

        # Get current player IDs from BB
        bb_player_ids = {p["player_id"] for p in bb_players}

        # Mark players not in roster as inactive
        stmt = select(Player).where(Player.current_team_id == team.id)
        result = await db.execute(stmt)
        existing_players = result.scalars().all()

        for player in existing_players:
            if player.player_id not in bb_player_ids:
                player.active = False

        # Update or create players
        synced_count = 0
        for bb_player in bb_players:
            stmt = select(Player).where(Player.player_id == bb_player["player_id"])
            result = await db.execute(stmt)
            player = result.scalar_one_or_none()

            if player:
                # Update existing player
                player.name = bb_player["name"]
                player.country = bb_player["nationality"]
                player.age = bb_player["age"]
                player.height = bb_player["height"]
                player.potential = bb_player["potential"]
                player.salary = bb_player["salary"]
                player.dmi = bb_player["dmi"]
                player.best_position = bb_player["best_position"]
                player.game_shape = bb_player["game_shape"]
                player.jump_shot = bb_player["jump_shot"]
                player.jump_range = bb_player["jump_range"]
                player.outside_defense = bb_player["outside_defense"]
                player.handling = bb_player["handling"]
                player.driving = bb_player["driving"]
                player.passing = bb_player["passing"]
                player.inside_shot = bb_player["inside_shot"]
                player.inside_defense = bb_player["inside_defense"]
                player.rebounding = bb_player["rebounding"]
                player.shot_blocking = bb_player["shot_blocking"]
                player.stamina = bb_player["stamina"]
                player.free_throws = bb_player["free_throws"]
                player.experience = bb_player["experience"]
                player.current_team_id = team.id
                player.active = True
            else:
                # Create new player
                player = Player(
                    player_id=bb_player["player_id"],
                    name=bb_player["name"],
                    country=bb_player["nationality"],
                    age=bb_player["age"],
                    height=bb_player["height"],
                    potential=bb_player["potential"],
                    salary=bb_player["salary"],
                    dmi=bb_player["dmi"],
                    best_position=bb_player["best_position"],
                    game_shape=bb_player["game_shape"],
                    jump_shot=bb_player["jump_shot"],
                    jump_range=bb_player["jump_range"],
                    outside_defense=bb_player["outside_defense"],
                    handling=bb_player["handling"],
                    driving=bb_player["driving"],
                    passing=bb_player["passing"],
                    inside_shot=bb_player["inside_shot"],
                    inside_defense=bb_player["inside_defense"],
                    rebounding=bb_player["rebounding"],
                    shot_blocking=bb_player["shot_blocking"],
                    stamina=bb_player["stamina"],
                    free_throws=bb_player["free_throws"],
                    experience=bb_player["experience"],
                    current_team_id=team.id,
                    active=True
                )
                db.add(player)

            synced_count += 1

        return synced_count

    except Exception as e:
        logger.error(f"Error syncing team {team.name}: {e}")
        return 0


MAX_CONCURRENT_SYNCS = 3  # Max users to sync in parallel


async def sync_user_rosters(user: User, semaphore: asyncio.Semaphore) -> tuple[int, int]:
    """Sync all rosters for a single user. Returns (teams_synced, players_synced)."""
    async with semaphore:  # Limit concurrency
        async with async_session() as db:
            try:
                # Get all teams for this user
                stmt = select(Team).where(Team.coach_id == user.id)
                result = await db.execute(stmt)
                teams = result.scalars().all()

                if not teams:
                    return 0, 0

                teams_synced = 0
                players_synced = 0

                # Use single HTTP client per user to maintain session
                async with httpx.AsyncClient() as http_client:
                    bb_client = BBApiClient(user.bb_key)

                    # Login first
                    try:
                        login_result = await bb_client.login_with_client(
                            user.login_name,
                            user.bb_key,
                            http_client
                        )
                        if not login_result.get("success"):
                            logger.error(f"Login failed for user {user.username}: {login_result.get('message')}")
                            return 0, 0
                        logger.info(f"Logged in as {user.username}")
                    except Exception as e:
                        logger.error(f"Login error for user {user.username}: {e}")
                        return 0, 0

                    # Sync each team
                    for team in teams:
                        logger.info(f"Syncing team {team.name} for user {user.username}")
                        synced = await sync_roster_for_team(user, team, db, http_client)
                        if synced > 0:
                            teams_synced += 1
                            players_synced += synced

                        # Small delay between teams to avoid rate limiting
                        await asyncio.sleep(1)

                await db.commit()
                return teams_synced, players_synced

            except Exception as e:
                logger.error(f"Error syncing user {user.username}: {e}")
                await db.rollback()
                return 0, 0


async def sync_all_rosters():
    """Sync rosters for all users who have auto_sync_enabled (parallel with limit)."""
    logger.info(f"Starting scheduled roster sync at {datetime.utcnow()}")

    async with async_session() as db:
        # Get all users with BB keys AND auto_sync_enabled
        stmt = select(User).where(
            User.bb_key.isnot(None),
            User.auto_sync_enabled == True
        )
        result = await db.execute(stmt)
        users = result.scalars().all()

    if not users:
        logger.info("No users with auto_sync_enabled found")
        return

    logger.info(f"Syncing {len(users)} users (max {MAX_CONCURRENT_SYNCS} concurrent)")

    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)

    # Run all user syncs in parallel (with semaphore limiting)
    results = await asyncio.gather(
        *[sync_user_rosters(user, semaphore) for user in users],
        return_exceptions=True
    )

    # Sum up results
    total_teams = 0
    total_players = 0
    for result in results:
        if isinstance(result, tuple):
            total_teams += result[0]
            total_players += result[1]
        elif isinstance(result, Exception):
            logger.error(f"Sync task failed: {result}")

    logger.info(f"Scheduled sync complete: {total_teams} teams, {total_players} players synced")


def start_scheduler():
    """Start the scheduler with Friday 1 PM CET job."""
    # CET is UTC+1 in winter, UTC+2 in summer (CEST)
    # For simplicity, use UTC+1 (12:00 UTC = 13:00 CET)
    # This will be 14:00 CEST in summer, but close enough
    scheduler.add_job(
        sync_all_rosters,
        CronTrigger(
            day_of_week='fri',
            hour=12,  # 12:00 UTC = 13:00 CET
            minute=0,
            timezone='UTC'
        ),
        id='weekly_roster_sync',
        name='Weekly roster sync for all users',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started - roster sync scheduled for every Friday at 13:00 CET")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")