"""User schema definition for backend APIs."""

from datetime import datetime

from app.utils.security import MIN_PWD_LEN
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for creating a user"""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Field(None, min_length=MIN_PWD_LEN)


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
