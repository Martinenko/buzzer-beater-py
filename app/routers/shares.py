from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_share import PlayerShare
from app.schemas.player_share import SharePlayerRequest, ShareResponse, PlayerShareDto, PlayerInShare
from app.schemas.user import UserSearchResult
from app.routers.user import get_current_user_from_cookie, get_current_team_id_from_cookie

router = APIRouter()


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
                recipient_id=recipient.id
            )
            db.add(share)
            shared_count += 1

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
            selectinload(PlayerShare.player),
            selectinload(PlayerShare.owner),
        )
        .where(PlayerShare.recipient_id == current_user.id)
    )
    result = await db.execute(stmt)
    shares = result.scalars().all()

    return [
        PlayerShareDto(
            share_id=share.id,
            player=PlayerInShare(
                id=share.player.id,
                player_id=share.player.player_id,
                name=share.player.name,
                age=share.player.age,
                potential=share.player.potential,
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
            owner_name=share.owner.name,
            owner_team_name=None,
            recipient_username=current_user.username,
            recipient_name=current_user.name,
            shared_at=share.created_at
        )
        for share in shares
    ]


@router.get("/sent", response_model=List[PlayerShareDto])
async def get_sent_shares(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get players I have shared"""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = (
        select(PlayerShare)
        .options(
            selectinload(PlayerShare.player),
            selectinload(PlayerShare.recipient),
        )
        .where(PlayerShare.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    shares = result.scalars().all()

    return [
        PlayerShareDto(
            share_id=share.id,
            player=PlayerInShare(
                id=share.player.id,
                player_id=share.player.player_id,
                name=share.player.name,
                age=share.player.age,
                potential=share.player.potential,
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
            owner_name=current_user.name,
            owner_team_name=None,
            recipient_username=share.recipient.username,
            recipient_name=share.recipient.name,
            shared_at=share.created_at
        )
        for share in shares
    ]


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


@router.get("/users/search", response_model=List[UserSearchResult])
async def search_users(
    q: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Search for users to share with by public username"""
    current_user = await get_current_user_from_cookie(request, db)

    if len(q) < 2:
        return []

    # Search only by public username
    stmt = (
        select(User)
        .where(
            User.username.ilike(f"%{q}%"),
            User.id != current_user.id
        )
        .limit(10)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    return [
        UserSearchResult(username=user.username, name=user.username)
        for user in users
    ]
