from pydantic import BaseModel
from typing import Optional
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
