# backend/app/routers/groups.py

from app.dependencies import get_current_user, get_group_service
from app.models import User
from app.models.group import GroupRole
from app.schemas.group import (
    AddMemberRequest,
    GroupCreate,
    GroupDetailResponse,
    GroupMemberResponse,
    GroupModifyRequest,
    GroupResponse,
    GroupSettingsResponse,
    GroupStatsResponse,
    JoinGroupResponse,
    RoleUpdateRequest,
)
from app.services.group_service import GroupService
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/groups", tags=["groups"])


# ==================== CRUD ====================


@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    group_data: GroupCreate,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Create a new group. The requesting user becomes the Owner."""
    return group_service.create_group(group_data, current_user)


@router.get("/search", response_model=list[GroupDetailResponse])
def search_groups(
    query: str | None = None,
    username: str | None = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Search public groups by partial name and/or member username."""
    groups = group_service.search_groups(query=query, username=username, limit=limit)
    return [
        GroupDetailResponse(
            id=g.id,
            name=g.name,
            created_at=g.created_at,
            is_public=g.is_public,
            member_count=len(g.members),
            current_user_role=(
                role.value if (role := group_service.get_user_role(current_user.id, g.id)) else None
            ),
            settings=GroupSettingsResponse.model_validate(g.settings) if g.settings else None,
        )
        for g in groups
    ]


@router.get("/name/{group_name}", response_model=GroupDetailResponse)
def get_group_by_name(
    group_name: str,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Get group by name (case-insensitive). Private groups require membership."""
    group = group_service.get_group_by_name(group_name)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if not group.is_public and not group_service.is_user_in_group(current_user.id, group.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    current_role = group_service.get_user_role(current_user.id, group.id)
    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        is_public=group.is_public,
        member_count=len(group.members),
        current_user_role=current_role.value if current_role else None,
        settings=GroupSettingsResponse.model_validate(group.settings) if group.settings else None,
    )


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Get group by ID. Private groups require membership."""
    group = group_service.get_group_by_id(group_id)
    if not group.is_public and not group_service.is_user_in_group(current_user.id, group_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    current_role = group_service.get_user_role(current_user.id, group_id)
    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        is_public=group.is_public,
        member_count=len(group.members),
        current_user_role=current_role.value if current_role else None,
        settings=GroupSettingsResponse.model_validate(group.settings) if group.settings else None,
    )


@router.patch("/{group_id}", response_model=GroupDetailResponse)
def update_group(
    group_id: int,
    update_data: GroupModifyRequest,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Update group settings. Requires Admin or Owner role."""
    group_service.update_group_settings(group_id, current_user.id, update_data)
    group = group_service.get_group_by_id(group_id)
    current_role = group_service.get_user_role(current_user.id, group_id)
    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        created_at=group.created_at,
        is_public=group.is_public,
        member_count=len(group.members),
        current_user_role=current_role.value if current_role else None,
        settings=GroupSettingsResponse.model_validate(group.settings) if group.settings else None,
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Delete a group. Requires Owner role."""
    group_service.delete_group(group_id, current_user.id)


# ==================== STATS ====================


@router.get("/{group_id}/stats", response_model=GroupStatsResponse)
def get_group_stats(
    group_id: int,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Get aggregate statistics for a group. Requires membership."""
    group_service.require_membership(current_user.id, group_id)
    return group_service.get_group_stats(group_id)


# ==================== MEMBERSHIP ====================


@router.post("/{group_id}/join", response_model=JoinGroupResponse)
def join_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Join a public group."""
    group = group_service.get_group_by_id(group_id)
    if not group.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot join a private group without an invitation",
        )
    group_service.add_user(group_id, current_user.id)
    joined_at = group_service.get_group_join_date(current_user.id, group_id)
    return JoinGroupResponse(joined_at=joined_at)


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    group_id: int,
    body: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Add a user to a group. Required role is configured per group (default: Admin or Owner)."""
    settings = group_service.get_group_settings(group_id)
    group_service.require_permission(
        current_user.id, group_id, GroupRole(settings.min_role_to_add_members)
    )
    group_service.add_user(group_id, body.user_id)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Remove a user from a group. Admins/Owners can remove others; members can remove themselves."""
    group_service.remove_user(group_id, user_id, current_user.id)


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
def list_members(
    group_id: int,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """List all members of a group. Requires membership."""
    group_service.require_membership(current_user.id, group_id)
    return group_service.get_group_members(group_id)


@router.get("/{group_id}/members/{user_id}", response_model=GroupMemberResponse)
def get_member(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Get a specific member's info (role, join date). Requires membership."""
    group_service.require_membership(current_user.id, group_id)
    members = group_service.get_group_members(group_id)
    member = next((m for m in members if m["user_id"] == user_id), None)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} is not a member of this group",
        )
    return member


# ==================== ROLES ====================


@router.put("/{group_id}/members/{user_id}/role", response_model=GroupMemberResponse)
def update_member_role(
    group_id: int,
    user_id: int,
    body: RoleUpdateRequest,
    current_user: User = Depends(get_current_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Update a member's role. Setter must hold a role >= the target role."""
    group_service.set_user_role(user_id, current_user.id, group_id, GroupRole(body.role))
    members = group_service.get_group_members(group_id)
    return next(m for m in members if m["user_id"] == user_id)
