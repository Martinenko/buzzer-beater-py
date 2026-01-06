from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
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
