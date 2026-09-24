"""Pydantic schemas for MasterProfile."""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class MasterProfileBase(BaseModel):
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    telegram_username: Optional[str] = None
    experience_years: Optional[int] = None


class MasterProfileCreate(MasterProfileBase):
    pass


class MasterProfileUpdate(BaseModel):
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    telegram_username: Optional[str] = None
    experience_years: Optional[int] = None


class MasterProfileResponse(MasterProfileBase):
    id: int
    user_id: int
    status: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
