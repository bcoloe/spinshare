# backend/app/routers/users.py

from app.dependencies import get_current_user, get_user_service
from app.models import User
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithStats,
)
from app.services.user_service import UserService
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, user_service: UserService = Depends(get_user_service)):
    """Register a new user"""
    return user_service.create_user(user_data)


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, user_service: UserService = Depends(get_user_service)):
    """Login and get access token"""
    return user_service.login(credentials.email, credentials.password)


@router.post("/refresh", response_model=LoginResponse)
def refresh_access_token(refresh_token: str, user_service: UserService = Depends(get_user_service)):
    """Exchange a valid REFRESH token for a new ACCESS token."""
    return user_service.refresh(refresh_token)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information via ACCESS token"""
    return current_user


@router.get("/me/stats", response_model=UserWithStats)
def get_my_stats(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get current user statistics"""
    stats = user_service.get_user_stats(current_user.id)
    return {**current_user.__dict__, **stats}


@router.put("/me", response_model=UserResponse)
def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Update current user information"""
    return user_service.update_user(current_user.id, user_data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Delete current user account"""
    user_service.delete_user(current_user.id)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, user_service: UserService = Depends(get_user_service)):
    """Get user by ID"""
    return user_service.get_user_by_id(user_id)


@router.get("/", response_model=list[UserResponse])
def list_users(
    skip: int = 0, limit: int = 100, user_service: UserService = Depends(get_user_service)
):
    """List all users"""
    return user_service.get_all_users(skip=skip, limit=limit)


@router.get("/search/{query}", response_model=list[UserResponse])
def search_users(
    query: str, limit: int = 10, user_service: UserService = Depends(get_user_service)
):
    """Search users by username or email"""
    return user_service.search_users(query, limit=limit)
