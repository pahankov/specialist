"""Pydantic schemas for ClientProfile."""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class ClientProfileBase(BaseModel):
    no_show_count: int = 0
    preferred_service_ids: Optional[List[int]] = None


class ClientProfileCreate(ClientProfileBase):
    pass


class ClientProfileUpdate(BaseModel):
    no_show_count: Optional[int] = None
    preferred_service_ids: Optional[List[int]] = None


class ClientProfileResponse(ClientProfileBase):
    id: int
    user_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
