# backend/app/schemas/invitation.py

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class InvitationStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"


class InvitationCreate(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def lowercase(cls, v):
        return v.lower() if v else v


class InvitationResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    invited_email: str
    invited_by: int
    inviter_username: str
    token: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    status: InvitationStatus

    model_config = ConfigDict(from_attributes=True)
