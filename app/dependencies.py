from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import get_settings
from app.models.user import User

settings = get_settings()
TOKEN_COOKIE_NAME = "bb_session"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from session cookie"""
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=403, detail="Not authenticated")

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        login_name: str = payload.get("sub")
        if login_name is None:
            raise HTTPException(status_code=403, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

    stmt = select(User).where(User.login_name == login_name)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=403, detail="User not found")

    return user


async def get_current_team_id(request: Request) -> int:
    """Get current team ID from session cookie"""
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=403, detail="Not authenticated")

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        team_id = payload.get("team_id")
        if team_id is None:
            raise HTTPException(status_code=400, detail="No team selected")
        return team_id
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")
