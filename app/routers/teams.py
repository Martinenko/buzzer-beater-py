from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.schemas.team import TeamInfo, TeamResponse
from app.dependencies import get_current_user, get_current_team_id
from app.services.bb_api import BBApiClient

router = APIRouter()


@router.get("/", response_model=List[TeamInfo])
async def get_user_teams(
    current_user: User = Depends(get_current_user),
    current_team_id: int = Depends(get_current_team_id),
    db: AsyncSession = Depends(get_db)
):
    """Get all teams for current user"""
    stmt = select(Team).where(Team.coach_id == current_user.id)
    result = await db.execute(stmt)
    teams = result.scalars().all()

    return [
        TeamInfo(
            team_id=team.team_id,
            name=team.name,
            short_name=team.short_name,
            team_type=team.team_type,
            active=(team.team_id == current_team_id)
        )
        for team in teams
    ]


@router.post("/switch/{team_id}")
async def switch_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Switch active team"""
    # Verify user owns this team
    stmt = select(Team).where(Team.team_id == team_id, Team.coach_id == current_user.id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # In a real implementation, you'd issue a new token with the new team_id
    # For now, just return success
    return {"success": True, "message": f"Switched to team {team.name}"}


@router.get("/economy")
async def get_economy(
    current_user: User = Depends(get_current_user),
    current_team_id: int = Depends(get_current_team_id)
):
    """Get team economy from BuzzerBeater API"""
    if not current_user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    bb_client = BBApiClient(current_user.bb_key)
    economy = await bb_client.get_economy(current_team_id)

    return economy
