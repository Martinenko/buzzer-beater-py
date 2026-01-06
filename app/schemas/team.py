from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from app.models.team import TeamType


class TeamInfo(BaseModel):
    team_id: int
    name: str
    short_name: str
    team_type: TeamType
    active: bool = False

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    id: UUID
    team_id: int
    name: str
    short_name: str
    team_type: TeamType
    league_name: Optional[str] = None
    country_name: Optional[str] = None

    class Config:
        from_attributes = True
