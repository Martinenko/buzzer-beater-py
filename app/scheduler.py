"""
Scheduled tasks for automatic roster synchronization.
Runs every Friday at 1 PM CET (12:00 UTC in winter, 11:00 UTC in summer).
"""
import asyncio
import logging
from datetime import datetime, timedelta
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_snapshot import PlayerSnapshot
from app.models.user_message import UserMessage
from app.models.user_thread import UserThread
from app.services.bb_api import BBApiClient
from app.services.email_service import email_service
from app.config import get_settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
settings = get_settings()


def get_current_bb_week() -> tuple[int, int]:
    """Get current BB week info. Returns (year, week_of_year).
    BB week starts on Friday and ends on Thursday."""
    now = datetime.utcnow()
    days_since_friday = (now.weekday() - 4) % 7
    start_of_week = now - timedelta(days=days_since_friday)
    year = start_of_week.isocalendar()[0]
    week = start_of_week.isocalendar()[1]
    return year, week


async def create_player_snapshots(team: Team, db: AsyncSession) -> int:
    """Create weekly snapshots for all active players on a team."""
    year, week = get_current_bb_week()

    # Get active players for this team
    stmt = select(Player).where(Player.current_team_id == team.id, Player.active == True)
    result = await db.execute(stmt)
    players = result.scalars().all()

    snapshots_created = 0
    for player in players:
        # Check if snapshot already exists for this week
        stmt = select(PlayerSnapshot).where(
            PlayerSnapshot.player_id == player.id,
            PlayerSnapshot.year == year,
            PlayerSnapshot.week_of_year == week
        )
        result = await db.execute(stmt)
        existing_snapshot = result.scalar_one_or_none()

        if existing_snapshot:
            # Update existing snapshot
            existing_snapshot.name = player.name
            existing_snapshot.country = player.country
            existing_snapshot.age = player.age
            existing_snapshot.height = player.height
            existing_snapshot.potential = player.potential
            existing_snapshot.game_shape = player.game_shape
            existing_snapshot.salary = player.salary
            existing_snapshot.dmi = player.dmi
            existing_snapshot.best_position = player.best_position
            existing_snapshot.jump_shot = player.jump_shot
            existing_snapshot.jump_range = player.jump_range
            existing_snapshot.outside_defense = player.outside_defense
            existing_snapshot.handling = player.handling
            existing_snapshot.driving = player.driving
            existing_snapshot.passing = player.passing
            existing_snapshot.inside_shot = player.inside_shot
            existing_snapshot.inside_defense = player.inside_defense
            existing_snapshot.rebounding = player.rebounding
            existing_snapshot.shot_blocking = player.shot_blocking
            existing_snapshot.stamina = player.stamina
            existing_snapshot.free_throws = player.free_throws
            existing_snapshot.experience = player.experience
        else:
            # Create new snapshot
            snapshot = PlayerSnapshot(
                player_id=player.id,
                bb_player_id=player.player_id,
                team_id=team.id,
                year=year,
                week_of_year=week,
                name=player.name,
                country=player.country,
                age=player.age,
                height=player.height,
                potential=player.potential,
                game_shape=player.game_shape,
                salary=player.salary,
                dmi=player.dmi,
                best_position=player.best_position,
                jump_shot=player.jump_shot,
                jump_range=player.jump_range,
                outside_defense=player.outside_defense,
                handling=player.handling,
                driving=player.driving,
                passing=player.passing,
                inside_shot=player.inside_shot,
                inside_defense=player.inside_defense,
                rebounding=player.rebounding,
                shot_blocking=player.shot_blocking,
                stamina=player.stamina,
                free_throws=player.free_throws,
                experience=player.experience,
            )
            db.add(snapshot)
            snapshots_created += 1

    return snapshots_created


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

                            # Create snapshots for this team
                            snapshots = await create_player_snapshots(team, db)
                            logger.info(f"Created {snapshots} snapshots for team {team.name}")

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


async def get_unread_dm_count_for_user(user: User, db: AsyncSession) -> int:
    delay_minutes = user.unread_reminder_delay_min or 60
    cutoff = datetime.utcnow() - timedelta(minutes=delay_minutes)

    stmt = (
        select(func.count(UserMessage.id))
        .select_from(UserMessage)
        .join(UserThread, UserThread.id == UserMessage.thread_id)
        .where(
            UserMessage.read_at.is_(None),
            UserMessage.sender_id != user.id,
            UserMessage.created_at <= cutoff,
            or_(UserThread.user_a_id == user.id, UserThread.user_b_id == user.id),
        )
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def send_unread_message_reminders():
    """Send grouped unread DM reminders with cooldown (max once per 24h per user)."""
    if not email_service.is_configured():
        logger.info("Skipping unread reminders: SMTP not configured")
        return

    logger.info("Starting unread DM reminder job")
    sent_count = 0

    async with async_session() as db:
        stmt = select(User).where(
            User.unread_reminder_enabled == True,
            User.email_verified == True,
            User.email.isnot(None),
        )
        result = await db.execute(stmt)
        users = result.scalars().all()

        for user in users:
            if user.last_unread_reminder_sent_at:
                if user.last_unread_reminder_sent_at > datetime.utcnow() - timedelta(hours=24):
                    continue

            unread_count = await get_unread_dm_count_for_user(user, db)
            if unread_count <= 0:
                continue

            open_url = f"{settings.web_app_url}/messages"
            delay = user.unread_reminder_delay_min or 60
            subject = f"You have {unread_count} unread message{'s' if unread_count != 1 else ''} on BB Scout"
            text = (
                f"Hi {user.username or user.login_name},\n\n"
                f"You still have {unread_count} unread direct message{'s' if unread_count != 1 else ''} "
                f"older than {delay} minutes.\n"
                f"Open conversations: {open_url}\n\n"
                "You can disable these reminders in your profile settings."
            )
            html = (
                f"<p>Hi {user.username or user.login_name},</p>"
                f"<p>You still have <strong>{unread_count}</strong> unread direct message"
                f"{'s' if unread_count != 1 else ''} older than {delay} minutes.</p>"
                f"<p><a href=\"{open_url}\">Open conversations</a></p>"
                "<p>You can disable these reminders in your profile settings.</p>"
            )

            try:
                await asyncio.to_thread(
                    email_service.send_email,
                    user.email,
                    subject,
                    text,
                    html,
                )
                user.last_unread_reminder_sent_at = datetime.utcnow()
                sent_count += 1
            except Exception as exc:
                logger.error(f"Failed to send reminder to {user.login_name}: {exc}")

        await db.commit()

    logger.info(f"Unread DM reminder job complete. Emails sent: {sent_count}")


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

    scheduler.add_job(
        send_unread_message_reminders,
        CronTrigger(minute='*/10', timezone='UTC'),
        id='unread_dm_email_reminders',
        name='Unread DM reminder emails',
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started - roster sync weekly + unread DM reminders every 10 minutes")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")