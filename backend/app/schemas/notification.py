# backend/app/schemas/notification.py

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class NotificationType(str, Enum):
    invitation_accepted = "invitation_accepted"
    invitation_declined = "invitation_declined"
    nomination_pool_low = "nomination_pool_low"
    member_reviewed_album = "member_reviewed_album"
    new_member_joined = "new_member_joined"


class NotificationResponse(BaseModel):
    id: int
    type: NotificationType
    message: str
    group_id: int | None
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
