# backend/app/schemas/invitation.py

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class InvitationStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"


class InvitationCreate(BaseModel):
    """Payload for inviting someone to a group.

    Exactly one of ``email`` or ``username`` must be supplied. ``username`` lets
    clients invite a user surfaced by search without ever learning their email.
    """

    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50)

    @field_validator("email", "username", mode="before")
    @classmethod
    def lowercase(cls, v):
        return v.lower() if v else v

    @model_validator(mode="after")
    def _exactly_one_identifier(self):
        if (self.email is None) == (self.username is None):
            raise ValueError("Exactly one of email or username must be specified.")
        return self


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
