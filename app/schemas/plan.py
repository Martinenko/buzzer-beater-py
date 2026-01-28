"""Schemas for player training plan."""
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _clamp_skill(v: Optional[int]) -> Optional[int]:
    if v is None:
        return None
    return max(1, min(20, v))


class PlanSkillsBase(BaseModel):
    """Target skills 1–20. Omit or null = no target."""

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

    @field_validator(
        "jump_shot", "jump_range", "outside_defense", "handling", "driving",
        "passing", "inside_shot", "inside_defense", "rebounding", "shot_blocking",
        "stamina", "free_throws", "experience",
        mode="before"
    )
    @classmethod
    def clamp_skill(cls, v: Optional[int]) -> Optional[int]:
        return _clamp_skill(v)


class PlanUpsert(PlanSkillsBase):
    """Request body for create/update plan. Accepts camelCase."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=_to_camel)


class PlanResponse(PlanSkillsBase):
    """Training plan response (camelCase in API)."""

    id: UUID
    player_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=_to_camel,
        serialize_by_alias=True,
    )
