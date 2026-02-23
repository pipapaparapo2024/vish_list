from datetime import datetime

from pydantic import BaseModel, Field


class ReservationCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    contact: str | None = Field(None, max_length=255)


class ReservationRead(BaseModel):
    id: int
    item_id: int
    display_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class ContributionCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    contact: str | None = Field(None, max_length=255)
    amount: float = Field(..., gt=0)


class ContributionRead(BaseModel):
    id: int
    item_id: int
    display_name: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True

