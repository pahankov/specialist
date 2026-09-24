from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


class ReviewCreate(BaseModel):
    appointment_id: int
    rating: float
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: float) -> float:
        if v < 1.0 or v > 5.0:
            raise ValueError("Rating must be between 1.0 and 5.0")
        return v


class ReviewResponse(BaseModel):
    id: int
    appointment_id: int
    master_id: int
    client_name: str
    client_phone: str
    rating: float
    comment: Optional[str]
    is_published: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewUpdate(BaseModel):
    comment: Optional[str] = None
    is_published: Optional[bool] = None
