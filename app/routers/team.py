from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.services.bb_api import BBApiClient
from app.routers.user import get_current_user_from_cookie, get_current_team_id_from_cookie, get_current_team_type_from_cookie

router = APIRouter()


@router.get("/economy")
async def get_economy(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get team economy from BuzzerBeater API (matches Spring API)"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)
    team_type = get_current_team_type_from_cookie(request)
    is_utopia = (team_type == "UTOPIA")

    if not user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    bb_client = BBApiClient(user.bb_key)
    economy = await bb_client.get_economy(current_team_id, username=user.login_name, is_utopia=is_utopia)

    return economy


@router.get("/roster")
async def get_roster(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get team roster (matches Spring API)"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)
    print(f"DEBUG roster: user={user.username}, team_id={current_team_id}")

    # Get team
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()
    print(f"DEBUG roster: team found={team is not None}")

    if not team:
        return []

    # Get players
    stmt = select(Player).where(Player.current_team_id == team.id, Player.active == True)
    result = await db.execute(stmt)
    players = result.scalars().all()
    print(f"DEBUG roster: players count={len(players)}")

    # Return in Spring format
    return [
        {
            "id": player.player_id,
            "name": player.name,
            "country": player.country,
            "age": player.age,
            "height": player.height,
            "salary": player.salary,
            "dmi": player.dmi,
            "bestPosition": player.best_position,
            "potential": player.potential,
            "gameShape": player.game_shape,
            "jumpShot": player.jump_shot,
            "jumpRange": player.jump_range,
            "outsideDefense": player.outside_defense,
            "handling": player.handling,
            "driving": player.driving,
            "passing": player.passing,
            "insideShot": player.inside_shot,
            "insideDefense": player.inside_defense,
            "rebounding": player.rebounding,
            "shotBlocking": player.shot_blocking,
            "stamina": player.stamina,
            "freeThrows": player.free_throws,
            "experience": player.experience,
            "archived": not player.active
        }
        for player in players
    ]


@router.get("/roster/sync")
async def sync_roster(
    request: Request,
    teamId: int = None,
    db: AsyncSession = Depends(get_db)
):
    """Sync roster from BuzzerBeater API (matches Spring API - GET not POST)"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = teamId or await get_current_team_id_from_cookie(request)

    if not user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    # Get team from database
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check if this is a UTOPIA team (needs secondteam=1 for BB API)
    is_utopia = (team.team_type.value == "UTOPIA")

    # Fetch roster from BB API
    bb_client = BBApiClient(user.bb_key)
    bb_players = await bb_client.get_roster(current_team_id, username=user.login_name, is_utopia=is_utopia)

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

    await db.commit()

    return {"success": True, "message": f"Synced {synced_count} players"}


@router.get("/snapshots")
async def get_snapshots(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get synced weeks/snapshots (matches Spring API)"""
    from datetime import datetime, timedelta

    # Return current week so Angular loads the roster
    now = datetime.utcnow()

    # BB week starts on Friday (weekday 4) and ends on Thursday (weekday 3)
    # Calculate days since last Friday
    days_since_friday = (now.weekday() - 4) % 7
    start_of_week = now - timedelta(days=days_since_friday)
    end_of_week = start_of_week + timedelta(days=6)  # Thursday

    # Use ISO week of the Friday start date
    year = start_of_week.isocalendar()[0]
    week = start_of_week.isocalendar()[1]

    return [{
        "year": year,
        "weekOfYear": week,
        "startDate": start_of_week.strftime("%Y-%m-%d"),
        "endDate": end_of_week.strftime("%Y-%m-%d")
    }]


@router.get("/roster/week")
async def get_roster_for_week(
    year: int,
    weekOfYear: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get roster for specific week (matches Spring API)"""
    # For now, just return current roster - implement snapshots later
    return await get_roster(request, db)
