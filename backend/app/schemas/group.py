"""Group schema definition for backend APIs."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_GROUP_NAME = 3
MAX_GROUP_NAME = 50


class GroupBase(BaseModel):
    """Base group schema"""

    name: str = Field(..., min_length=MIN_GROUP_NAME, max_length=MAX_GROUP_NAME)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        pattern = re.compile(r"^[A-Za-z0-9_-]+$")
        if not bool(pattern.fullmatch(v)):
            raise ValueError("May only be alphanumeric with -_")
        return v


class GroupCreate(GroupBase):
    """Group creation schema"""

    pass


class GroupResponse(GroupBase):
    """Schema for group response"""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JoinGroupRequest(BaseModel):
    """Join group request schema"""

    id: int


class JoinGroupResponse(BaseModel):
    """Join group response"""

    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)
