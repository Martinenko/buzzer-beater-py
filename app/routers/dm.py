from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.user_thread import UserThread
from app.models.user_message import UserMessage
from app.routers.user import get_current_user_from_cookie
from app.ws import manager
from app.routers.user import TOKEN_COOKIE_NAME, settings
from jose import jwt
from sqlalchemy import select

router = APIRouter()


def to_camel(string: str) -> str:
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class CreateDmRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    recipient_username: str


class SendDmRequest(BaseModel):
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
    participant_id: UUID
    participant_username: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None
    unread_count: int = 0


class ThreadDetailDto(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: UUID
    participant_id: UUID
    participant_username: str
    is_active: bool
    messages: List[MessageDto]


def _get_unread_count(thread: UserThread, current_user_id: UUID) -> int:
    return sum(1 for msg in thread.messages if msg.sender_id != current_user_id and msg.read_at is None)


def _make_message_dto(msg: UserMessage, current_user_id: UUID) -> MessageDto:
    return MessageDto(
        id=msg.id,
        content=msg.content,
        sender_id=msg.sender_id,
        sender_username=msg.sender.username or msg.sender.login_name,
        created_at=msg.created_at,
        is_mine=msg.sender_id == current_user_id,
        is_read=msg.read_at is not None,
    )


@router.get("", response_model=List[ThreadDto])
async def get_my_dms(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user_from_cookie(request, db)

    stmt = (
        select(UserThread)
        .options(selectinload(UserThread.messages), selectinload(UserThread.user_a), selectinload(UserThread.user_b))
        .where(or_(UserThread.user_a_id == current_user.id, UserThread.user_b_id == current_user.id))
        .order_by(UserThread.updated_at.desc())
    )
    result = await db.execute(stmt)
    threads = result.scalars().all()

    out = []
    for thread in threads:
        # choose the other participant
        other = thread.user_a if thread.user_a_id != current_user.id else thread.user_b
        out.append(
            ThreadDto(
                id=thread.id,
                participant_id=other.id,
                participant_username=other.username or other.login_name,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                last_message=thread.messages[-1].content if thread.messages else None,
                unread_count=_get_unread_count(thread, current_user.id),
            )
        )

    return out


@router.post("", response_model=ThreadDetailDto)
async def create_or_get_dm(request: Request, body: CreateDmRequest, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user_from_cookie(request, db)

    # find recipient
    stmt = select(User).where(User.username == body.recipient_username)
    result = await db.execute(stmt)
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    if recipient.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot DM yourself")

    # order ids to match unique constraint
    a_id, b_id = (current_user.id, recipient.id) if str(current_user.id) < str(recipient.id) else (recipient.id, current_user.id)

    stmt = select(UserThread).where(UserThread.user_a_id == a_id, UserThread.user_b_id == b_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        thread = UserThread(user_a_id=a_id, user_b_id=b_id, is_active=True)
        db.add(thread)
        await db.commit()
        await db.refresh(thread)

    # load messages
    stmt = select(UserThread).options(selectinload(UserThread.messages), selectinload(UserThread.user_a), selectinload(UserThread.user_b)).where(UserThread.id == thread.id)
    result = await db.execute(stmt)
    thread = result.scalar_one()

    other = thread.user_a if thread.user_a_id != current_user.id else thread.user_b

    return ThreadDetailDto(
        id=thread.id,
        participant_id=other.id,
        participant_username=other.username or other.login_name,
        is_active=thread.is_active,
        messages=[_make_message_dto(m, current_user.id) for m in thread.messages],
    )


@router.get("/{thread_id}", response_model=ThreadDetailDto)
async def get_dm(thread_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user_from_cookie(request, db)

    stmt = select(UserThread).options(selectinload(UserThread.messages).selectinload(UserMessage.sender), selectinload(UserThread.user_a), selectinload(UserThread.user_b)).where(UserThread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # ensure user is participant
    if current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=403, detail="Not a participant in this thread")

    other = thread.user_a if thread.user_a_id != current_user.id else thread.user_b

    # mark messages read
    stmt = (
        update(UserMessage)
        .where(UserMessage.thread_id == thread.id, UserMessage.sender_id != current_user.id, UserMessage.read_at.is_(None))
        .values(read_at=datetime.utcnow())
    )
    await db.execute(stmt)
    await db.commit()

    # reload messages
    stmt = select(UserThread).options(selectinload(UserThread.messages).selectinload(UserMessage.sender), selectinload(UserThread.user_a), selectinload(UserThread.user_b)).where(UserThread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one()

    return ThreadDetailDto(
        id=thread.id,
        participant_id=other.id,
        participant_username=other.username or other.login_name,
        is_active=thread.is_active,
        messages=[_make_message_dto(m, current_user.id) for m in thread.messages],
    )


@router.post("/{thread_id}/messages", response_model=MessageDto)
async def send_dm(thread_id: UUID, body: SendDmRequest, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user_from_cookie(request, db)

    stmt = select(UserThread).where(UserThread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=403, detail="Not a participant in this thread")

    msg = UserMessage(thread_id=thread.id, sender_id=current_user.id, content=body.content)
    db.add(msg)
    # update thread updated_at
    thread.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)

    # Notify other participant via websocket (if connected)
    other_id = thread.user_a_id if thread.user_a_id != current_user.id else thread.user_b_id
    payload = {
        "event": "dm:new_message",
        "threadId": str(thread.id),
        "message": {
            "id": str(msg.id),
            "content": msg.content,
            "senderId": str(msg.sender_id),
            "senderUsername": current_user.username or current_user.login_name,
            "createdAt": msg.created_at.isoformat(),
        }
    }
    # fire and forget
    try:
        await manager.send_json_to_user(str(other_id), payload)
    except Exception:
        pass
    # publish to Redis so other instances can forward to their connected sockets
    try:
        await manager.publish('dm:events', {'target_user_id': str(other_id), 'payload': payload})
    except Exception:
        # non-fatal
        pass

    return _make_message_dto(msg, current_user.id)



@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    """WebSocket endpoint for receiving DM events. Authenticates using session cookie."""
    await websocket.accept()
    # Attempt to read cookie token
    token = websocket.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        login_name = payload.get("sub")
    except Exception:
        await websocket.close(code=1008)
        return

    # Load user from DB
    stmt = select(User).where(User.login_name == login_name)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        await websocket.close(code=1008)
        return

    user_id = str(user.id)
    await manager.connect(user_id, websocket)

    try:
        while True:
            # Keep connection alive; we don't expect client messages for now
            data = await websocket.receive_text()
            # Optionally, handle ping or presence messages in future
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
    except Exception:
        await manager.disconnect(user_id, websocket)
