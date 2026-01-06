from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.team import Team, TeamType
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.bb_api import BBApiClient

router = APIRouter()
settings = get_settings()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with BuzzerBeater credentials"""

    # Call BuzzerBeater API to authenticate
    bb_client = BBApiClient()
    result = await bb_client.login(request.username, request.password)

    if not result.get("success"):
        return LoginResponse(
            success=False,
            message=result.get("message", "Login failed")
        )

    # Get or create user
    stmt = select(User).where(User.username == result["username"])
    db_result = await db.execute(stmt)
    user = db_result.scalar_one_or_none()

    if not user:
        user = User(
            username=result["username"],
            bb_key=result["bb_key"],
            supporter=result.get("supporter", False)
        )
        db.add(user)
    else:
        user.bb_key = result["bb_key"]
        user.supporter = result.get("supporter", False)

    await db.commit()
    await db.refresh(user)

    # Create or update teams
    first_team_id = None
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

    await db.commit()

    # Create JWT token
    access_token = create_access_token(
        data={"sub": user.username, "team_id": first_team_id}
    )

    return LoginResponse(
        success=True,
        message="Login successful",
        access_token=access_token
    )


@router.post("/logout")
async def logout():
    """Logout (client should discard token)"""
    return {"success": True, "message": "Logged out"}
