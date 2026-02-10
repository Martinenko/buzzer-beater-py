from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime


def to_camel(string: str) -> str:
    parts = string.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])


class SharePlayerRequest(BaseModel):
    recipient_username: str = Field(alias="recipientUsername")
    player_ids: List[int] = Field(default=[], alias="playerIds")
    share_entire_team: bool = Field(default=False, alias="shareEntireTeam")
    share_plan: bool = Field(default=False, alias="sharePlan")

    model_config = ConfigDict(populate_by_name=True)


class ShareResponse(BaseModel):
    success: bool
    message: str
    shared_count: int = Field(default=0, alias="sharedCount")

    model_config = ConfigDict(populate_by_name=True, by_alias=True)


class PlayerInShare(BaseModel):
    id: UUID
    player_id: int = Field(alias="playerId")
    name: str
    age: Optional[int] = None
    potential: int = 0
    best_position: Optional[str] = Field(default=None, alias="bestPosition")

    # Skills - using camelCase aliases
    jump_shot: Optional[int] = Field(default=None, alias="jumpShot")
    jump_range: Optional[int] = Field(default=None, alias="jumpRange")
    outside_defense: Optional[int] = Field(default=None, alias="outsideDefense")
    handling: Optional[int] = None
    driving: Optional[int] = None
    passing: Optional[int] = None
    inside_shot: Optional[int] = Field(default=None, alias="insideShot")
    inside_defense: Optional[int] = Field(default=None, alias="insideDefense")
    rebounding: Optional[int] = None
    shot_blocking: Optional[int] = Field(default=None, alias="shotBlocking")
    stamina: Optional[int] = None
    free_throws: Optional[int] = Field(default=None, alias="freeThrows")
    experience: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class PlayerShareDto(BaseModel):
    share_id: UUID = Field(alias="shareId")
    player: PlayerInShare
    owner_username: str = Field(alias="ownerUsername")
    owner_name: Optional[str] = Field(default=None, alias="ownerName")
    owner_team_name: Optional[str] = Field(default=None, alias="ownerTeamName")
    owner_team_id: Optional[int] = Field(default=None, alias="ownerTeamId")
    recipient_username: str = Field(alias="recipientUsername")
    recipient_name: Optional[str] = Field(default=None, alias="recipientName")
    shared_at: datetime = Field(alias="sharedAt")
    share_plan: bool = Field(default=False, alias="sharePlan")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, by_alias=True)


class UpdateShareRequest(BaseModel):
    share_plan: bool = Field(alias="sharePlan")
    model_config = ConfigDict(populate_by_name=True)
