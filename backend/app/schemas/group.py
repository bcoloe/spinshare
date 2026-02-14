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

    is_public: bool = True


class GroupResponse(GroupBase):
    """Schema for group response"""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupModifyRequest(BaseModel):
    """Schema for modifying group metadata"""

    name: str | None = None
    is_public: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is None:
            return v
        if len(v) < MIN_GROUP_NAME or len(v) > MAX_GROUP_NAME:
            raise ValueError(f"Character limit violation [{MIN_GROUP_NAME}, {MAX_GROUP_NAME}]")
        pattern = re.compile(r"^[A-Za-z0-9_-]+$")
        if not bool(pattern.fullmatch(v)):
            raise ValueError("May only be alphanumeric with -_")
        return v


class JoinGroupRequest(BaseModel):
    """Join group request schema"""

    id: int


class JoinGroupResponse(BaseModel):
    """Join group response"""

    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)
