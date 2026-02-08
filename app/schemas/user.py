from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from uuid import UUID


class UserCreate(BaseModel):
    username: str
    bb_key: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    username: str
    name: Optional[str] = None
    supporter: bool = False

    class Config:
        from_attributes = True


class UserSearchResult(BaseModel):
    username: str
    name: Optional[str] = None

    class Config:
        from_attributes = True


class UserSearchResponse(BaseModel):
    users: List[UserSearchResult]
    has_more: bool = Field(alias="hasMore", default=False)

    model_config = ConfigDict(populate_by_name=True, by_alias=True)
