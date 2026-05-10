from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InviteLinkResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    created_by: int
    creator_username: str
    token: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
