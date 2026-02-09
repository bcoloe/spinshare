"""User schema definition for backend APIs."""

from datetime import datetime

from app.utils.security import MAX_PWD_LEN, MIN_PWD_LEN, validate_password_strength
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for creating a user"""

    password: str = Field(..., min_length=MIN_PWD_LEN, max_length=MAX_PWD_LEN)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        is_valid, reasons = validate_password_strength(v)
        if not is_valid:
            reasons_str = "\n".join([" * " + x for x in reasons])
            raise ValueError(reasons_str)
        return v


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Field(None, min_length=MIN_PWD_LEN, max_length=MAX_PWD_LEN)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        is_valid, reasons = validate_password_strength(v)
        if not is_valid:
            reasons_str = "\n".join([" * " + x for x in reasons])
            raise ValueError(reasons_str)
        return v


class UserResponse(UserBase):
    """Schema for user response (without password)"""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserWithStats(UserResponse):
    """User response with statistics"""

    total_groups: int
    created_groups: int
    total_reviews: int
    albums_added: int
    has_spotify: bool


class LoginRequest(BaseModel):
    """Schema for login request"""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Schema for login response"""

    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse
