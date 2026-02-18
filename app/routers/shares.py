from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_share import PlayerShare
from app.models.player_snapshot import PlayerSnapshot
from app.models.player_training_plan import PlayerTrainingPlan
from app.models.user_thread import UserThread
from app.models.user_message import UserMessage
from app.schemas.player_share import SharePlayerRequest, ShareResponse, PlayerShareDto, PlayerInShare, UpdateShareRequest, PlayerSnapshotDto, PlanTargets
from app.schemas.user import UserSearchResult, UserSearchResponse
from app.routers.user import get_current_user_from_cookie, get_current_team_id_from_cookie

router = APIRouter()


def _snapshot_to_dto(snapshot: PlayerSnapshot | None) -> PlayerSnapshotDto | None:
    if snapshot is None:
        return None
    return PlayerSnapshotDto(
        year=snapshot.year,
        week_of_year=snapshot.week_of_year,
        jump_shot=snapshot.jump_shot,
        jump_range=snapshot.jump_range,
        outside_defense=snapshot.outside_defense,
        handling=snapshot.handling,
        driving=snapshot.driving,
        passing=snapshot.passing,
        inside_shot=snapshot.inside_shot,
        inside_defense=snapshot.inside_defense,
        rebounding=snapshot.rebounding,
        shot_blocking=snapshot.shot_blocking,
        stamina=snapshot.stamina,
        free_throws=snapshot.free_throws,
        experience=snapshot.experience,
    )


def _plan_to_targets(plan: PlayerTrainingPlan | None) -> PlanTargets | None:
    if plan is None:
        return None
    return PlanTargets(
        jump_shot=plan.jump_shot,
        jump_range=plan.jump_range,
        outside_defense=plan.outside_defense,
        handling=plan.handling,
        driving=plan.driving,
        passing=plan.passing,
        inside_shot=plan.inside_shot,
        inside_defense=plan.inside_defense,
        rebounding=plan.rebounding,
        shot_blocking=plan.shot_blocking,
        stamina=plan.stamina,
        free_throws=plan.free_throws,
        experience=plan.experience,
    )


async def _get_latest_snapshots(db: AsyncSession, player_id: UUID) -> tuple[PlayerSnapshot | None, PlayerSnapshot | None]:
    stmt = (
        select(PlayerSnapshot)
        .where(PlayerSnapshot.player_id == player_id)
        .order_by(PlayerSnapshot.year.desc(), PlayerSnapshot.week_of_year.desc())
        .limit(2)
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    latest = snapshots[0] if len(snapshots) > 0 else None
    previous = snapshots[1] if len(snapshots) > 1 else None
    return latest, previous


@router.post("", response_model=ShareResponse)
async def share_players(
    share_request: SharePlayerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Share players with another user"""
    current_user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)

    # Find recipient
    stmt = select(User).where(User.username == share_request.recipient_username)
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()

    if not recipient:
        return ShareResponse(success=False, message="User not found")

    if recipient.id == current_user.id:
        return ShareResponse(success=False, message="Cannot share with yourself")

    # Get team
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        return ShareResponse(success=False, message="Team not found")

    # Get players to share
    if share_request.share_entire_team:
        stmt = select(Player).where(Player.current_team_id == team.id, Player.active == True)
    else:
        stmt = select(Player).where(Player.player_id.in_(share_request.player_ids))

    result = await db.execute(stmt)
    players = result.scalars().all()

    if not players:
        return ShareResponse(success=False, message="No players found to share")

    # Create shares
    shared_count = 0
    for player in players:
        # Check if share already exists
        stmt = select(PlayerShare).where(
            PlayerShare.player_id == player.id,
            PlayerShare.recipient_id == recipient.id
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            share = PlayerShare(
                player_id=player.id,
                owner_id=current_user.id,
                recipient_id=recipient.id,
                share_plan=share_request.share_plan,
                message=share_request.message,
            )
            db.add(share)
            shared_count += 1

    await db.commit()

    # Create DM notification if players were shared
    if shared_count > 0:
        owner_name = current_user.username or current_user.login_name
        team_name = team.name if team else "unknown"
        
        # Format players as markdown links with ID, one per line
        players_list = "\n".join([f"• [{p.name} ({p.player_id})](/players/{p.player_id})" for p in players])
        
        notification_content = (
            f"{owner_name} shared {shared_count} player{'s' if shared_count != 1 else ''} "
            f"from {team_name} team with you:\n\n"
            f"{players_list}"
        )
        if share_request.message:
            notification_content += f"\n\nMessage: {share_request.message}"

        # Get or create DM thread between the two users
        a_id, b_id = (current_user.id, recipient.id) if str(current_user.id) < str(recipient.id) else (recipient.id, current_user.id)
        stmt = select(UserThread).where(UserThread.user_a_id == a_id, UserThread.user_b_id == b_id)
        result = await db.execute(stmt)
        dm_thread = result.scalar_one_or_none()
        if not dm_thread:
            dm_thread = UserThread(user_a_id=a_id, user_b_id=b_id, is_active=True)
            db.add(dm_thread)
            await db.commit()
            await db.refresh(dm_thread)

        dm_msg = UserMessage(
            thread_id=dm_thread.id,
            sender_id=current_user.id,
            content=notification_content,
        )
        db.add(dm_msg)
        await db.commit()

    return ShareResponse(
        success=True,
        message=f"Shared {shared_count} players with {recipient.username}",
        shared_count=shared_count
    )


@router.get("/received", response_model=List[PlayerShareDto])
async def get_received_shares(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get players shared with me"""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = (
        select(PlayerShare)
        .options(
            selectinload(PlayerShare.player).selectinload(Player.current_team),
            selectinload(PlayerShare.owner),
        )
        .where(PlayerShare.recipient_id == current_user.id)
    )
    result = await db.execute(stmt)
    shares = result.scalars().all()

    # Prefetch teams to ensure ownerTeamId/Name are available even if relationship isn't loaded
    team_ids = {s.player.current_team_id for s in shares if s.player and s.player.current_team_id}
    owner_ids = {s.owner_id for s in shares}
    team_map = {}
    teams_by_owner = {}
    teams_by_owner_name = {}
    if team_ids or owner_ids:
        team_query = select(Team).where(or_(Team.id.in_(team_ids), Team.coach_id.in_(owner_ids)))
        team_result = await db.execute(team_query)
        teams = team_result.scalars().all()
        team_map = {t.id: t for t in teams}
        for t in teams:
            teams_by_owner.setdefault(t.coach_id, []).append(t)
            teams_by_owner_name[(t.coach_id, t.name)] = t
    def resolve_owner_team(share: PlayerShare) -> tuple[int | None, str | None]:
        if share.player.current_team:
            return share.player.current_team.team_id, share.player.current_team.name
        if share.player.current_team_id and team_map.get(share.player.current_team_id):
            team = team_map.get(share.player.current_team_id)
            return team.team_id, team.name
        if share.player.team_name and teams_by_owner_name.get((share.owner_id, share.player.team_name)):
            team = teams_by_owner_name.get((share.owner_id, share.player.team_name))
            return team.team_id, team.name
        owner_teams = teams_by_owner.get(share.owner_id, [])
        if len(owner_teams) == 1:
            return owner_teams[0].team_id, owner_teams[0].name
        return None, None

    out: list[PlayerShareDto] = []
    for share in shares:
        team_id, team_name = resolve_owner_team(share)
        latest_snapshot, previous_snapshot = await _get_latest_snapshots(db, share.player.id)
        plan_targets = None
        if share.share_plan:
            plan_result = await db.execute(
                select(PlayerTrainingPlan).where(PlayerTrainingPlan.player_id == share.player.id)
            )
            plan_targets = _plan_to_targets(plan_result.scalar_one_or_none())
        out.append(PlayerShareDto(
            share_id=share.id,
            player=PlayerInShare(
                id=share.player.id,
                player_id=share.player.player_id,
                name=share.player.name,
                age=share.player.age,
                potential=share.player.potential or 0,
                best_position=share.player.best_position,
                jump_shot=share.player.jump_shot,
                jump_range=share.player.jump_range,
                outside_defense=share.player.outside_defense,
                handling=share.player.handling,
                driving=share.player.driving,
                passing=share.player.passing,
                inside_shot=share.player.inside_shot,
                inside_defense=share.player.inside_defense,
                rebounding=share.player.rebounding,
                shot_blocking=share.player.shot_blocking,
                stamina=share.player.stamina,
                free_throws=share.player.free_throws,
                experience=share.player.experience,
            ),
            owner_username=share.owner.username,
            owner_name=share.owner.username,
            owner_team_name=team_name,
            owner_team_id=team_id,
            recipient_username=current_user.username,
            recipient_name=current_user.username,
            shared_at=share.created_at,
            share_plan=share.share_plan,
            message=share.message,
            latest_snapshot=_snapshot_to_dto(latest_snapshot),
            previous_snapshot=_snapshot_to_dto(previous_snapshot),
            plan_targets=plan_targets,
        ))

    return out


@router.get("/sent", response_model=List[PlayerShareDto])
async def get_sent_shares(
    request: Request,
    player_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get players I have shared. Optional player_id filter (BB player ID)."""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = (
        select(PlayerShare)
        .options(
            selectinload(PlayerShare.player).selectinload(Player.current_team),
            selectinload(PlayerShare.recipient),
        )
        .where(PlayerShare.owner_id == current_user.id)
    )
    if player_id is not None:
        stmt = stmt.join(Player, PlayerShare.player_id == Player.id).where(Player.player_id == player_id)
    result = await db.execute(stmt)
    shares = result.scalars().all()

    team_ids = {s.player.current_team_id for s in shares if s.player and s.player.current_team_id}
    owner_ids = {s.owner_id for s in shares}
    team_map = {}
    teams_by_owner = {}
    teams_by_owner_name = {}
    if team_ids or owner_ids:
        team_query = select(Team).where(or_(Team.id.in_(team_ids), Team.coach_id.in_(owner_ids)))
        team_result = await db.execute(team_query)
        teams = team_result.scalars().all()
        team_map = {t.id: t for t in teams}
        for t in teams:
            teams_by_owner.setdefault(t.coach_id, []).append(t)
            teams_by_owner_name[(t.coach_id, t.name)] = t
    def resolve_owner_team(share: PlayerShare) -> tuple[int | None, str | None]:
        if share.player.current_team:
            return share.player.current_team.team_id, share.player.current_team.name
        if share.player.current_team_id and team_map.get(share.player.current_team_id):
            team = team_map.get(share.player.current_team_id)
            return team.team_id, team.name
        if share.player.team_name and teams_by_owner_name.get((share.owner_id, share.player.team_name)):
            team = teams_by_owner_name.get((share.owner_id, share.player.team_name))
            return team.team_id, team.name
        owner_teams = teams_by_owner.get(share.owner_id, [])
        if len(owner_teams) == 1:
            return owner_teams[0].team_id, owner_teams[0].name
        return None, None

    out: list[PlayerShareDto] = []
    for share in shares:
        team_id, team_name = resolve_owner_team(share)
        latest_snapshot, previous_snapshot = await _get_latest_snapshots(db, share.player.id)
        plan_targets = None
        if share.share_plan:
            plan_result = await db.execute(
                select(PlayerTrainingPlan).where(PlayerTrainingPlan.player_id == share.player.id)
            )
            plan_targets = _plan_to_targets(plan_result.scalar_one_or_none())
        out.append(PlayerShareDto(
            share_id=share.id,
            player=PlayerInShare(
                id=share.player.id,
                player_id=share.player.player_id,
                name=share.player.name,
                age=share.player.age,
                potential=share.player.potential or 0,
                best_position=share.player.best_position,
                jump_shot=share.player.jump_shot,
                jump_range=share.player.jump_range,
                outside_defense=share.player.outside_defense,
                handling=share.player.handling,
                driving=share.player.driving,
                passing=share.player.passing,
                inside_shot=share.player.inside_shot,
                inside_defense=share.player.inside_defense,
                rebounding=share.player.rebounding,
                shot_blocking=share.player.shot_blocking,
                stamina=share.player.stamina,
                free_throws=share.player.free_throws,
                experience=share.player.experience,
            ),
            owner_username=current_user.username,
            owner_name=current_user.username,
            owner_team_name=team_name,
            owner_team_id=team_id,
            recipient_username=share.recipient.username,
            recipient_name=share.recipient.username,
            shared_at=share.created_at,
            share_plan=share.share_plan,
            message=share.message,
            latest_snapshot=_snapshot_to_dto(latest_snapshot),
            previous_snapshot=_snapshot_to_dto(previous_snapshot),
            plan_targets=plan_targets,
        ))

    return out


@router.delete("/{share_id}")
async def remove_share(
    share_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Remove a share"""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = select(PlayerShare).where(
        PlayerShare.id == share_id,
        PlayerShare.owner_id == current_user.id
    )
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="Share not found")

    await db.delete(share)
    await db.commit()

    return {"success": True, "message": "Share removed"}


@router.patch("/{share_id}")
async def update_share(
    share_id: UUID,
    body: UpdateShareRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update share settings (e.g. share_plan toggle). Owner only."""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = select(PlayerShare).where(
        PlayerShare.id == share_id,
        PlayerShare.owner_id == current_user.id,
    )
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="Share not found")

    share.share_plan = body.share_plan
    await db.commit()

    return {"success": True}


@router.get("/users/search", response_model=UserSearchResponse)
async def search_users(
    request: Request,
    q: str = "",
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Search for users to share with by public username"""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = select(User).where(User.id != current_user.id)

    if q:
        stmt = stmt.where(User.username.ilike(f"%{q}%"))

    stmt = stmt.order_by(User.username.asc()).offset(offset).limit(limit + 1)

    result = await db.execute(stmt)
    users = result.scalars().all()

    has_more = len(users) > limit
    users = users[:limit]

    return UserSearchResponse(
        users=[
            UserSearchResult(username=user.username, name=user.username)
            for user in users
        ],
        hasMore=has_more,
    )
