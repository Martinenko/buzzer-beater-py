"""Player training plan API. Only for own players."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_training_plan import PlayerTrainingPlan
from app.schemas.plan import PlanUpsert, PlanResponse
from app.dependencies import get_current_user

router = APIRouter()

_SKILL_ATTRS = [
    "jump_shot", "jump_range", "outside_defense", "handling", "driving", "passing",
    "inside_shot", "inside_defense", "rebounding", "shot_blocking",
    "stamina", "free_throws", "experience",
]


async def _get_owned_player(db: AsyncSession, user: User, player_id: int) -> Player:
    """Resolve BB player_id to Player and ensure current user owns them."""
    stmt = select(Player).options(selectinload(Player.current_team)).where(
        Player.player_id == player_id
    )
    result = await db.execute(stmt)
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    stmt = select(Team.id).where(Team.coach_id == user.id)
    result = await db.execute(stmt)
    user_team_ids = [r[0] for r in result.all()]
    if player.current_team_id not in user_team_ids:
        raise HTTPException(status_code=403, detail="Not your player")

    return player


def _plan_to_response(plan: PlayerTrainingPlan, bb_player_id: int) -> PlanResponse:
    data = {
        "id": plan.id,
        "player_id": bb_player_id,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }
    for attr in _SKILL_ATTRS:
        data[attr] = getattr(plan, attr, None)
    return PlanResponse.model_validate(data)


@router.get("/player/{player_id}", response_model=PlanResponse)
async def get_plan(
    player_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get training plan for a player. 404 if none."""
    player = await _get_owned_player(db, current_user, player_id)

    stmt = select(PlayerTrainingPlan).where(PlayerTrainingPlan.player_id == player.id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No plan for this player")

    return _plan_to_response(plan, player.player_id)


@router.put("/player/{player_id}", response_model=PlanResponse)
async def upsert_plan(
    player_id: int,
    body: PlanUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update training plan for a player."""
    player = await _get_owned_player(db, current_user, player_id)

    stmt = select(PlayerTrainingPlan).where(PlayerTrainingPlan.player_id == player.id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if plan:
        for attr in _SKILL_ATTRS:
            setattr(plan, attr, getattr(body, attr, None))
    else:
        plan = PlayerTrainingPlan(
            player_id=player.id,
            **{a: getattr(body, a, None) for a in _SKILL_ATTRS},
        )
        db.add(plan)

    await db.commit()
    await db.refresh(plan)
    return _plan_to_response(plan, player.player_id)


@router.delete("/player/{player_id}", status_code=204)
async def delete_plan(
    player_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove training plan for a player."""
    player = await _get_owned_player(db, current_user, player_id)

    stmt = select(PlayerTrainingPlan).where(PlayerTrainingPlan.player_id == player.id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()
    if plan:
        await db.delete(plan)
        await db.commit()
