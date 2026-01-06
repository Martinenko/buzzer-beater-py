from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class SharePlayerRequest(BaseModel):
    recipient_username: str = Field(alias="recipientUsername")
    player_ids: List[int] = Field(alias="playerIds")
    share_entire_team: bool = Field(default=False, alias="shareEntireTeam")

    class Config:
        populate_by_name = True


class ShareResponse(BaseModel):
    success: bool
    message: str
    shared_count: int = 0


class PlayerInShare(BaseModel):
    id: UUID
    player_id: int
    name: str
    age: Optional[int] = None
    potential: int
    best_position: Optional[str] = None

    # Skills
    jump_shot: Optional[int] = None
    jump_range: Optional[int] = None
    outside_defense: Optional[int] = None
    handling: Optional[int] = None
    driving: Optional[int] = None
    passing: Optional[int] = None
    inside_shot: Optional[int] = None
    inside_defense: Optional[int] = None
    rebounding: Optional[int] = None
    shot_blocking: Optional[int] = None
    stamina: Optional[int] = None
    free_throws: Optional[int] = None
    experience: Optional[int] = None

    class Config:
        from_attributes = True


class PlayerShareDto(BaseModel):
    share_id: UUID
    player: PlayerInShare
    owner_username: str
    owner_name: Optional[str] = None
    owner_team_name: Optional[str] = None
    recipient_username: str
    recipient_name: Optional[str] = None
    shared_at: datetime

    class Config:
        from_attributes = True
