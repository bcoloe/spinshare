"""Group schema definition for backend APIs."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_GROUP_NAME = 3
MAX_GROUP_NAME = 50
MAX_DAILY_ALBUM_COUNT = 10
MIN_GUESS_USER_CAP = 3
MAX_GUESS_USER_CAP = 10


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


class GroupSettingsResponse(BaseModel):
    """Schema for group policy settings"""

    min_role_to_add_members: str
    daily_album_count: int
    allow_guessing: bool
    guess_user_cap: int

    model_config = ConfigDict(from_attributes=True)


class GroupSettingsUpdate(BaseModel):
    """Schema for updating group policy settings"""

    min_role_to_add_members: str | None = None
    daily_album_count: int | None = None
    guess_user_cap: int | None = None

    @field_validator("min_role_to_add_members")
    @classmethod
    def validate_role(cls, v):
        if v is None:
            return v
        valid = {"owner", "admin", "member"}
        if v.lower() not in valid:
            raise ValueError(f"Must be one of: {', '.join(sorted(valid))}")
        return v.lower()

    @field_validator("daily_album_count")
    @classmethod
    def validate_count(cls, v):
        if v is None:
            return v
        if v < 1 or v > MAX_DAILY_ALBUM_COUNT:
            raise ValueError(f"Must be between 1 and {MAX_DAILY_ALBUM_COUNT}")
        return v

    @field_validator("guess_user_cap")
    @classmethod
    def validate_guess_user_cap(cls, v):
        if v is None:
            return v
        if v < MIN_GUESS_USER_CAP or v > MAX_GUESS_USER_CAP:
            raise ValueError(f"Must be between {MIN_GUESS_USER_CAP} and {MAX_GUESS_USER_CAP}")
        return v


class GroupModifyRequest(BaseModel):
    """Schema for modifying group metadata and policy settings"""

    name: str | None = None
    is_public: bool | None = None
    settings: GroupSettingsUpdate | None = None

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


class GroupDetailResponse(GroupResponse):
    """Extended group response with visibility, member count, and policy settings"""

    is_public: bool
    is_global: bool
    member_count: int
    current_user_role: str | None = None
    settings: GroupSettingsResponse | None = None


class GroupMemberResponse(BaseModel):
    """Schema for a single group member"""

    user_id: int
    username: str
    role: str
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupStatsResponse(BaseModel):
    """Aggregate statistics for a group"""

    member_count: int
    albums_added: int
    albums_reviewed: int
    formed_at: datetime


class RoleUpdateRequest(BaseModel):
    """Schema for updating a member's role"""

    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        valid = {"owner", "admin", "member"}
        if v.lower() not in valid:
            raise ValueError(f"Must be one of: {', '.join(sorted(valid))}")
        return v.lower()


class AddMemberRequest(BaseModel):
    """Schema for adding a user to a group by admin"""

    user_id: int


class JoinGroupRequest(BaseModel):
    """Join group request schema"""

    id: int


class JoinGroupResponse(BaseModel):
    """Join group response"""

    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)
