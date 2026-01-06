from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class PlayerBase(BaseModel):
    player_id: int
    name: str
    country: str
    age: Optional[int] = None
    height: int
    potential: int
    best_position: Optional[str] = None
    salary: Optional[int] = None
    dmi: Optional[int] = None

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


class PlayerCreate(PlayerBase):
    game_shape: int = 0
    team_name: Optional[str] = None


class PlayerResponse(PlayerBase):
    id: UUID
    active: bool = True

    class Config:
        from_attributes = True


class PlayerRosterResponse(BaseModel):
    id: UUID
    player_id: int
    first_name: str
    last_name: str
    nationality: str
    age: Optional[int]
    height: int
    salary: Optional[int]
    dmi: Optional[int]
    best_position: Optional[str]
    archived: bool = False
    skills: dict

    class Config:
        from_attributes = True
