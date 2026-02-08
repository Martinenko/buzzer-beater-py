from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_thread import PlayerThread
from app.models.player_message import PlayerMessage
from app.routers.user import get_current_user_from_cookie

router = APIRouter()


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


# Pydantic models for request/response
class CreateThreadRequest(BaseModel):
    player_id: int  # BB player_id


class SendMessageRequest(BaseModel):
    content: str


class MessageDto(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID
    content: str
    sender_id: UUID
    sender_username: str
    created_at: datetime
    is_mine: bool
    is_read: bool


class ThreadDto(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID
    player_id: int
    player_name: str
    owner_id: UUID
    owner_username: str
    participant_id: UUID
    participant_username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None
    unread_count: int = 0
    is_owner: bool  # True if current user is owner


class ThreadDetailDto(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID
    player_id: int
    player_name: str
    owner_id: UUID
    owner_username: str
    participant_id: UUID
    participant_username: str
    is_active: bool
    is_owner: bool
    messages: List[MessageDto]


def _get_unread_count(thread: PlayerThread, current_user_id: UUID) -> int:
    """Count messages not sent by current user that haven't been read."""
    return sum(
        1 for msg in thread.messages
        if msg.sender_id != current_user_id and msg.read_at is None
    )


def _make_message_dto(msg: PlayerMessage, current_user_id: UUID) -> MessageDto:
    return MessageDto(
        id=msg.id,
        content=msg.content,
        sender_id=msg.sender_id,
        sender_username=msg.sender.username or msg.sender.login_name,
        created_at=msg.created_at,
        is_mine=msg.sender_id == current_user_id,
        is_read=msg.read_at is not None,
    )


async def _mark_messages_read(db: AsyncSession, thread_id: UUID, current_user_id: UUID) -> None:
    """Mark all messages in a thread as read for the current user (messages not sent by them)."""
    stmt = (
        update(PlayerMessage)
        .where(
            PlayerMessage.thread_id == thread_id,
            PlayerMessage.sender_id != current_user_id,
            PlayerMessage.read_at.is_(None),
        )
        .values(read_at=datetime.utcnow())
    )
    await db.execute(stmt)
    await db.commit()


@router.get("", response_model=List[ThreadDto])
async def get_my_threads(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get all threads for current user (as owner or participant)."""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = (
        select(PlayerThread)
        .options(
            selectinload(PlayerThread.player),
            selectinload(PlayerThread.owner),
            selectinload(PlayerThread.participant),
            selectinload(PlayerThread.messages),
        )
        .where(
            or_(
                PlayerThread.owner_id == current_user.id,
                PlayerThread.participant_id == current_user.id
            )
        )
        .order_by(PlayerThread.updated_at.desc())
    )
    result = await db.execute(stmt)
    threads = result.scalars().all()

    return [
        ThreadDto(
            id=thread.id,
            player_id=thread.player.player_id,
            player_name=thread.player.name,
            owner_id=thread.owner_id,
            owner_username=thread.owner.username or thread.owner.login_name,
            participant_id=thread.participant_id,
            participant_username=thread.participant.username or thread.participant.login_name,
            is_active=thread.is_active,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            last_message=thread.messages[-1].content if thread.messages else None,
            unread_count=_get_unread_count(thread, current_user.id),
            is_owner=thread.owner_id == current_user.id
        )
        for thread in threads
    ]


@router.get("/player/{player_id}/as-owner", response_model=List[ThreadDto])
async def get_threads_for_player_as_owner(
    player_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get all threads for a player where current user is the owner."""
    current_user = await get_current_user_from_cookie(request, db)

    # Find player
    stmt = select(Player).options(selectinload(Player.current_team)).where(Player.player_id == player_id)
    result = await db.execute(stmt)
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get all threads for this player where current user is owner
    stmt = (
        select(PlayerThread)
        .options(
            selectinload(PlayerThread.player),
            selectinload(PlayerThread.owner),
            selectinload(PlayerThread.participant),
            selectinload(PlayerThread.messages),
        )
        .where(
            PlayerThread.player_id == player.id,
            PlayerThread.owner_id == current_user.id,
            PlayerThread.is_active == True
        )
        .order_by(PlayerThread.updated_at.desc())
    )
    result = await db.execute(stmt)
    threads = result.scalars().all()

    return [
        ThreadDto(
            id=thread.id,
            player_id=thread.player.player_id,
            player_name=thread.player.name,
            owner_id=thread.owner_id,
            owner_username=thread.owner.username or thread.owner.login_name,
            participant_id=thread.participant_id,
            participant_username=thread.participant.username or thread.participant.login_name,
            is_active=thread.is_active,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            last_message=thread.messages[-1].content if thread.messages else None,
            unread_count=_get_unread_count(thread, current_user.id),
            is_owner=True
        )
        for thread in threads
    ]


@router.get("/player/{player_id}", response_model=Optional[ThreadDetailDto])
async def get_thread_for_player(
    player_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get thread for specific player between current user and player owner."""
    current_user = await get_current_user_from_cookie(request, db)

    # Find player
    stmt = select(Player).options(selectinload(Player.current_team)).where(Player.player_id == player_id)
    result = await db.execute(stmt)
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get owner of the player
    if not player.current_team:
        raise HTTPException(status_code=400, detail="Player has no team")

    stmt = select(Team).options(selectinload(Team.coach)).where(Team.id == player.current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team or not team.coach:
        raise HTTPException(status_code=400, detail="Player owner not found")

    owner = team.coach

    # Determine if current user is owner or participant
    if current_user.id == owner.id:
        # Current user is owner - use as-owner endpoint instead
        return None

    # Find existing thread
    stmt = (
        select(PlayerThread)
        .options(
            selectinload(PlayerThread.player),
            selectinload(PlayerThread.owner),
            selectinload(PlayerThread.participant),
            selectinload(PlayerThread.messages).selectinload(PlayerMessage.sender),
        )
        .where(
            PlayerThread.player_id == player.id,
            PlayerThread.owner_id == owner.id,
            PlayerThread.participant_id == current_user.id,
            PlayerThread.is_active == True
        )
    )
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        return None

    # Build response before marking as read so we know which were unread
    response = ThreadDetailDto(
        id=thread.id,
        player_id=thread.player.player_id,
        player_name=thread.player.name,
        owner_id=thread.owner_id,
        owner_username=thread.owner.username or thread.owner.login_name,
        participant_id=thread.participant_id,
        participant_username=thread.participant.username or thread.participant.login_name,
        is_active=thread.is_active,
        is_owner=thread.owner_id == current_user.id,
        messages=[
            _make_message_dto(msg, current_user.id)
            for msg in thread.messages
        ]
    )

    # Mark messages as read
    await _mark_messages_read(db, thread.id, current_user.id)

    return response


@router.post("/player/{player_id}", response_model=ThreadDetailDto)
async def create_or_get_thread(
    player_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Create or get existing thread for a player."""
    current_user = await get_current_user_from_cookie(request, db)

    # Find player
    stmt = select(Player).options(selectinload(Player.current_team)).where(Player.player_id == player_id)
    result = await db.execute(stmt)
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get owner of the player
    if not player.current_team:
        raise HTTPException(status_code=400, detail="Player has no team")

    stmt = select(Team).options(selectinload(Team.coach)).where(Team.id == player.current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team or not team.coach:
        raise HTTPException(status_code=400, detail="Player owner not found")

    owner = team.coach

    if current_user.id == owner.id:
        raise HTTPException(status_code=400, detail="Cannot create thread for your own player")

    # Check for existing active thread
    stmt = (
        select(PlayerThread)
        .options(
            selectinload(PlayerThread.player),
            selectinload(PlayerThread.owner),
            selectinload(PlayerThread.participant),
            selectinload(PlayerThread.messages).selectinload(PlayerMessage.sender),
        )
        .where(
            PlayerThread.player_id == player.id,
            PlayerThread.owner_id == owner.id,
            PlayerThread.participant_id == current_user.id,
            PlayerThread.is_active == True
        )
    )
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        # Create new thread
        thread = PlayerThread(
            player_id=player.id,
            owner_id=owner.id,
            participant_id=current_user.id
        )
        db.add(thread)
        await db.commit()
        await db.refresh(thread)

        # Reload with relationships
        stmt = (
            select(PlayerThread)
            .options(
                selectinload(PlayerThread.player),
                selectinload(PlayerThread.owner),
                selectinload(PlayerThread.participant),
                selectinload(PlayerThread.messages).selectinload(PlayerMessage.sender),
            )
            .where(PlayerThread.id == thread.id)
        )
        result = await db.execute(stmt)
        thread = result.scalar_one()

    return ThreadDetailDto(
        id=thread.id,
        player_id=thread.player.player_id,
        player_name=thread.player.name,
        owner_id=thread.owner_id,
        owner_username=thread.owner.username or thread.owner.login_name,
        participant_id=thread.participant_id,
        participant_username=thread.participant.username or thread.participant.login_name,
        is_active=thread.is_active,
        is_owner=thread.owner_id == current_user.id,
        messages=[
            _make_message_dto(msg, current_user.id)
            for msg in thread.messages
        ]
    )


@router.get("/{thread_id}", response_model=ThreadDetailDto)
async def get_thread(
    thread_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get thread by ID with all messages."""
    current_user = await get_current_user_from_cookie(request, db)

    stmt = (
        select(PlayerThread)
        .options(
            selectinload(PlayerThread.player),
            selectinload(PlayerThread.owner),
            selectinload(PlayerThread.participant),
            selectinload(PlayerThread.messages).selectinload(PlayerMessage.sender),
        )
        .where(
            PlayerThread.id == thread_id,
            or_(
                PlayerThread.owner_id == current_user.id,
                PlayerThread.participant_id == current_user.id
            )
        )
    )
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Build response before marking as read so we know which were unread
    response = ThreadDetailDto(
        id=thread.id,
        player_id=thread.player.player_id,
        player_name=thread.player.name,
        owner_id=thread.owner_id,
        owner_username=thread.owner.username or thread.owner.login_name,
        participant_id=thread.participant_id,
        participant_username=thread.participant.username or thread.participant.login_name,
        is_active=thread.is_active,
        is_owner=thread.owner_id == current_user.id,
        messages=[
            _make_message_dto(msg, current_user.id)
            for msg in thread.messages
        ]
    )

    # Mark messages as read
    await _mark_messages_read(db, thread.id, current_user.id)

    return response


@router.post("/{thread_id}/messages", response_model=MessageDto)
async def send_message(
    thread_id: UUID,
    message_request: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Send a message to a thread."""
    current_user = await get_current_user_from_cookie(request, db)

    # Find thread and verify access
    stmt = (
        select(PlayerThread)
        .where(
            PlayerThread.id == thread_id,
            or_(
                PlayerThread.owner_id == current_user.id,
                PlayerThread.participant_id == current_user.id
            )
        )
    )
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if not thread.is_active:
        raise HTTPException(status_code=400, detail="Thread is archived")

    # Create message
    message = PlayerMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        content=message_request.content.strip()
    )
    db.add(message)

    # Update thread's updated_at
    thread.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(message)

    return MessageDto(
        id=message.id,
        content=message.content,
        sender_id=message.sender_id,
        sender_username=current_user.username or current_user.login_name,
        created_at=message.created_at,
        is_mine=True,
        is_read=False,
    )
