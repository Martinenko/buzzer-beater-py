from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
from app.database import get_db
from app.models.nt_match_boxscore import NTMatchBoxscore, NTMatchTeamBoxscore
from app.models.player import Player
from typing import Optional

router = APIRouter()

@router.get("/nt/teams")
async def list_nt_teams(
    nt_type: str = Query(..., regex="^(senior|junior)$"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(
            NTMatchTeamBoxscore.team_id,
            NTMatchTeamBoxscore.team_name,
            NTMatchTeamBoxscore.short_name,
        )
        .join(NTMatchBoxscore, NTMatchBoxscore.match_id == NTMatchTeamBoxscore.match_id)
        .where(NTMatchTeamBoxscore.team_id.isnot(None))
    )

    if nt_type == "junior":
        query = query.where(
            or_(
                NTMatchBoxscore.match_type.ilike("%u21%"),
                NTMatchBoxscore.match_type.ilike("%junior%"),
                NTMatchTeamBoxscore.team_name.ilike("%u21%"),
            )
        )
    else:
        query = query.where(
            and_(
                ~NTMatchBoxscore.match_type.ilike("%u21%"),
                ~NTMatchBoxscore.match_type.ilike("%junior%"),
                ~NTMatchTeamBoxscore.team_name.ilike("%u21%"),
            )
        )

    if search:
        query = query.where(NTMatchTeamBoxscore.team_name.ilike(f"%{search}%"))

    query = query.distinct().order_by(NTMatchTeamBoxscore.team_name.asc())
    result = await db.execute(query)

    teams = result.all()
    return [
        {
            "teamId": team_id,
            "name": team_name,
            "country": short_name or "",
            "type": nt_type
        } for team_id, team_name, short_name in teams
    ]

from fastapi import Query

@router.get("/nt/teams/{team_id}/schedule")
async def get_nt_team_schedule(
    team_id: int,
    match_id: int = Query(None),
    db: AsyncSession = Depends(get_db)
):
    team_result = await db.execute(
        select(NTMatchTeamBoxscore.team_name)
        .where(NTMatchTeamBoxscore.team_id == team_id)
        .order_by(NTMatchTeamBoxscore.id.desc())
        .limit(1)
    )
    team_name = team_result.scalar_one_or_none() or f"Team {team_id}"

    query = (
        select(NTMatchBoxscore)
        .join(NTMatchTeamBoxscore, NTMatchTeamBoxscore.match_id == NTMatchBoxscore.match_id)
        .where(NTMatchTeamBoxscore.team_id == team_id)
    )
    if match_id:
        query = query.where(NTMatchBoxscore.match_id == match_id)
    query = query.order_by(NTMatchBoxscore.start_time.desc(), NTMatchBoxscore.match_id.desc())

    result = await db.execute(query)
    matches = result.scalars().all()
    return {
        "teamId": team_id,
        "teamName": team_name,
        "matches": [
            {
                "matchId": m.match_id,
                "type": m.match_type,
                "start": m.start_time,
                "end": m.end_time
            } for m in matches
        ]
    }

@router.get("/nt/players/{player_id}")
async def get_nt_player_detail(
    player_id: int,
    db: AsyncSession = Depends(get_db)
):
    player = await db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {
        "playerId": player.player_id,
        "name": player.name,
        "country": player.country,
        "age": player.age,
        "height": player.height,
        "potential": player.potential,
        "gameShape": player.game_shape,
        "salary": player.salary,
        "dmi": player.dmi,
        "bestPosition": player.best_position,
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
            "experience": player.experience
        }
    }
