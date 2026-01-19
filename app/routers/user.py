from fastapi import APIRouter, Depends, HTTPException, Response, Request, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional, List

from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.team import Team, TeamType
from app.services.bb_api import BBApiClient

router = APIRouter()
settings = get_settings()

TOKEN_COOKIE_NAME = "bb_session"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


async def get_current_user_from_cookie(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user from session cookie"""
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        login_name = payload.get("sub")
        if not login_name:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    stmt = select(User).where(User.login_name == login_name)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_current_team_id_from_cookie(request: Request) -> int:
    """Get current team ID from session cookie"""
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        team_id = payload.get("team_id")
        if not team_id:
            raise HTTPException(status_code=400, detail="No team selected")
        return team_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_team_type_from_cookie(request: Request) -> str:
    """Get current team type (MAIN or UTOPIA) from session cookie"""
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        return "MAIN"

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("team_type", "MAIN")
    except JWTError:
        return "MAIN"


@router.get("/login")
async def login(
    username: str,
    bbKey: str,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login with BuzzerBeater credentials (matches Spring API)"""

    # Call BuzzerBeater API to authenticate
    bb_client = BBApiClient()
    result = await bb_client.login(username, bbKey)

    if not result.get("success"):
        return {"success": False, "message": result.get("message", "Login failed")}

    # Use login name from API response, fallback to input username
    actual_login_name = result.get("login_name") or username

    # Get public username from API response (owner element)
    public_username = result.get("username") or username

    # Get or create user
    stmt = select(User).where(User.login_name == actual_login_name)
    db_result = await db.execute(stmt)
    user = db_result.scalar_one_or_none()

    if not user:
        user = User(
            login_name=actual_login_name,
            username=public_username,
            bb_key=result.get("bb_key") or bbKey,
            supporter=result.get("supporter", False)
        )
        db.add(user)
    else:
        user.bb_key = result.get("bb_key") or bbKey
        user.username = public_username  # Update public username
        user.supporter = result.get("supporter", False)

    await db.commit()
    await db.refresh(user)

    # Create or update teams
    first_team_id = None
    first_team_type = "MAIN"
    for team_data in result.get("teams", []):
        stmt = select(Team).where(Team.team_id == team_data["team_id"])
        team_result = await db.execute(stmt)
        team = team_result.scalar_one_or_none()

        if not team:
            team = Team(
                team_id=team_data["team_id"],
                name=team_data["name"],
                short_name=team_data["name"][:3].upper(),
                team_type=TeamType(team_data["team_type"]),
                coach_id=user.id
            )
            db.add(team)
        else:
            team.name = team_data["name"]
            team.coach_id = user.id

        if first_team_id is None:
            first_team_id = team_data["team_id"]
            first_team_type = team_data["team_type"]

    await db.commit()

    # Create JWT token and set as cookie (use login_name for auth)
    # Include team_type so we know if it's UTOPIA (needs secondteam=1 for BB API)
    access_token = create_access_token(
        data={"sub": user.login_name, "team_id": first_team_id, "team_type": first_team_type}
    )

    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax"
    )

    return {"success": True, "message": "Login successful"}


@router.get("/teams")
async def get_user_teams(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get all teams for current user (matches Spring API)"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)

    stmt = select(Team).where(Team.coach_id == user.id)
    result = await db.execute(stmt)
    teams = result.scalars().all()

    return [
        {
            "teamId": team.team_id,
            "name": team.name,
            "teamType": team.team_type.value,
            "active": (team.team_id == current_team_id)
        }
        for team in teams
    ]


@router.post("/switch-team")
async def switch_team(
    teamId: int,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Switch active team (matches Spring API)"""
    user = await get_current_user_from_cookie(request, db)

    # Verify user owns this team
    stmt = select(Team).where(Team.team_id == teamId, Team.coach_id == user.id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Create new token with updated team_id and team_type (use login_name for auth)
    access_token = create_access_token(
        data={"sub": user.login_name, "team_id": teamId, "team_type": team.team_type.value}
    )

    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax"
    )

    return {"success": True, "message": f"Switched to team {team.name}"}


@router.post("/logout")
async def logout(response: Response):
    """Logout (matches Spring API)"""
    response.delete_cookie(key=TOKEN_COOKIE_NAME)
    return {"success": True, "message": "Logged out"}


@router.get("/me")
async def get_current_user_info(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current user info"""
    user = await get_current_user_from_cookie(request, db)
    return {
        "username": user.username or user.login_name,
        "supporter": user.supporter or False,
        "autoSyncEnabled": user.auto_sync_enabled or False
    }


@router.get("/settings")
async def get_user_settings(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current user settings"""
    user = await get_current_user_from_cookie(request, db)
    return {
        "autoSyncEnabled": user.auto_sync_enabled or False
    }


@router.post("/settings")
async def update_user_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    autoSyncEnabled: bool = None
):
    """Update user settings"""
    user = await get_current_user_from_cookie(request, db)

    if autoSyncEnabled is not None:
        user.auto_sync_enabled = autoSyncEnabled

    await db.commit()

    return {
        "success": True,
        "autoSyncEnabled": user.auto_sync_enabled or False
    }
