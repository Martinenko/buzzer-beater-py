from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_share import PlayerShare
from app.schemas.player import PlayerResponse, PlayerRosterResponse
from app.dependencies import get_current_user, get_current_team_id
from app.services.bb_api import BBApiClient

router = APIRouter()


@router.get("/roster", response_model=List[dict])
async def get_roster(
    show_archived: bool = False,
    current_user: User = Depends(get_current_user),
    current_team_id: int = Depends(get_current_team_id),
    db: AsyncSession = Depends(get_db)
):
    """Get team roster from database"""
    # Get team
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        return []

    # Get players
    stmt = select(Player).where(Player.current_team_id == team.id)
    if not show_archived:
        stmt = stmt.where(Player.active == True)

    result = await db.execute(stmt)
    players = result.scalars().all()

    return [
        {
            "id": str(player.id),
            "playerId": player.player_id,
            "firstName": player.name.split()[0] if player.name else "",
            "lastName": " ".join(player.name.split()[1:]) if player.name and len(player.name.split()) > 1 else "",
            "nationality": player.country,
            "age": player.age,
            "height": player.height,
            "salary": player.salary,
            "dmi": player.dmi,
            "bestPosition": player.best_position,
            "potential": player.potential,
            "archived": not player.active,
            "skills": {
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
            }
        }
        for player in players
    ]


@router.post("/sync")
async def sync_roster(
    current_user: User = Depends(get_current_user),
    current_team_id: int = Depends(get_current_team_id),
    db: AsyncSession = Depends(get_db)
):
    """Sync roster from BuzzerBeater API"""
    if not current_user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    # Get team from database
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Fetch roster from BB API
    bb_client = BBApiClient(current_user.bb_key)
    bb_players = await bb_client.get_roster(current_team_id)

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


@router.get("/all")
async def get_all_players(
    shared_only: bool = False,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    current_team_id: int = Depends(get_current_team_id),
    db: AsyncSession = Depends(get_db)
):
    """Get all players except those from current user's teams (paginated)"""
    from sqlalchemy import func

    # Get all teams owned by current user
    stmt = select(Team.id).where(Team.coach_id == current_user.id)
    result = await db.execute(stmt)
    user_team_ids = [row[0] for row in result.all()]

    # Get shares where current user is recipient
    shares_stmt = select(PlayerShare.player_id).where(
        PlayerShare.recipient_id == current_user.id
    )
    shares_result = await db.execute(shares_stmt)
    shared_player_ids = {row[0] for row in shares_result.all()}

    # Build base query for players
    if shared_only:
        if not shared_player_ids:
            return {"players": [], "total": 0, "page": page, "pageSize": page_size, "totalPages": 0}
        base_query = select(Player).where(
            Player.id.in_(shared_player_ids)
        )
    else:
        if user_team_ids:
            base_query = select(Player).where(
                Player.active == True,
                Player.current_team_id.notin_(user_team_ids)
            )
        else:
            base_query = select(Player).where(
                Player.active == True
            )

    # Get total count
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    stmt = base_query.options(selectinload(Player.current_team)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    players = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return {
        "players": [
            {
                "id": str(player.id),
                "playerId": player.player_id,
                "name": player.name,
                "country": player.country,
                "teamName": player.current_team.name if player.current_team else None,
                "age": player.age,
                "height": player.height,
                "bestPosition": player.best_position,
                "potential": player.potential,
                "isSharedWithMe": player.id in shared_player_ids,
                "skills": {
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
                } if player.id in shared_player_ids else None,
            }
            for player in players
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages
    }


@router.get("/{player_id}")
async def get_player(
    player_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get player details by BuzzerBeater player_id.

    Access control:
    - Own player: full access (skills, salary, dmi, gameShape)
    - Shared player: full access
    - Other player: public info only (no skills, salary, dmi, gameShape)
    """
    # Find player by BB player_id
    stmt = select(Player).options(selectinload(Player.current_team)).where(
        Player.player_id == player_id
    )
    result = await db.execute(stmt)
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get all teams owned by current user
    stmt = select(Team.id).where(Team.coach_id == current_user.id)
    result = await db.execute(stmt)
    user_team_ids = [row[0] for row in result.all()]

    # Check if player is owned by current user
    is_own_player = player.current_team_id in user_team_ids

    # Check if player is shared with current user
    is_shared_player = False
    if not is_own_player:
        share_stmt = select(PlayerShare).where(
            PlayerShare.player_id == player.id,
            PlayerShare.recipient_id == current_user.id
        )
        share_result = await db.execute(share_stmt)
        is_shared_player = share_result.scalar_one_or_none() is not None

    has_full_access = is_own_player or is_shared_player

    # Build response
    response = {
        "id": str(player.id),
        "playerId": player.player_id,
        "name": player.name,
        "country": player.country,
        "teamName": player.current_team.name if player.current_team else None,
        "teamId": player.current_team.team_id if player.current_team else None,
        "age": player.age,
        "height": player.height,
        "bestPosition": player.best_position,
        "potential": player.potential,
        "hasFullAccess": has_full_access,
        "isOwnPlayer": is_own_player,
        "isSharedPlayer": is_shared_player,
    }

    if has_full_access:
        response["salary"] = player.salary
        response["dmi"] = player.dmi
        response["gameShape"] = player.game_shape
        response["skills"] = {
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
        }
    else:
        response["salary"] = None
        response["dmi"] = None
        response["gameShape"] = None
        response["skills"] = None

    return response
