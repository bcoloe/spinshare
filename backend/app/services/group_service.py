"""Group service."""

from datetime import datetime

from app.models import Group, User, group_members
from app.models.group import GroupRole
from app.schemas.group import GroupCreate, GroupModifyRequest
from app.services import user_service
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class GroupService:
    """Service layer for Group operations"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create_group(self, group_data: GroupCreate, user: User) -> Group:
        """Create a new group.

        Raises:
            HTTPException 409 if group name already exists
        """
        existing_group = self.get_group_by_name(group_data.name)

        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Group name already registered"
            )

        # Create group
        group = Group(name=group_data.name, created_by=user.id, is_public=group_data.is_public)

        try:
            self.db.add(group)
            self.db.commit()
            self.db.refresh(group)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Group creation failed due to constraint violation",
            ) from None

        self.add_user(group.id, user.id)
        self.set_user_role(user.id, user.id, group.id, GroupRole.Owner, force=True)
        return group

    # ==================== ADD ====================

    def add_user(self, group_id: int, user_id: int):
        """Add a user to the group."""
        if self.is_user_in_group(user_id, group_id):
            return None
        group = self.get_group_by_id(group_id)
        user = user_service.UserService(self.db).get_user_by_id(user_id)
        group.members.append(user)
        try:
            self.db.add(group)
            self.db.commit()
            self.db.refresh(group)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Add user failed due to constraint violation",
            ) from None

    # ==================== DELETE ====================

    def delete_group(self, group_id: int, deleted_by_user_id: int) -> Group:
        """Delete an existing group.

        TODO: add notification hooks for all group members impacted to send email
        """
        self.require_permission(deleted_by_user_id, group_id, GroupRole.Owner)

        group = self.get_group_by_id(group_id)
        try:
            self.db.delete(group)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete group due to existing dependencies",
            ) from None

    def remove_user(self, group_id: int, user_id: int, removed_by_user_id: int):
        """Remove a user from a group.

        Raises:
            HTTPException 403 if user is not authorized to remove (i.e., >=admin or owner themselves)
        """
        group = self.get_group_by_id(group_id)
        if not self.is_user_in_group(user_id, group_id):
            # Member isn't in the group
            return None

        user = user_service.UserService(self.db).get_user_by_id(user_id)
        user_role = self.get_user_role(user_id, group_id)

        # Only allow removal by group creator OR member
        if removed_by_user_id != user_id:
            self.require_permission(removed_by_user_id, group_id, min(GroupRole.Admin, user_role))
        elif user_role == GroupRole.Owner:
            if len(self.get_users_with_role(group_id, GroupRole.Owner)) == 1:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot remove the only group owner -- nominate a replacement first",
                )

        try:
            group.members.remove(user)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove user due to existing dependencies",
            ) from None

    # ==================== GET ====================
    def get_group_by_id(self, group_id: int) -> Group:
        """Get group by ID.

        Raises:
            HTTPException 404: If group not found.
        """
        group = self.db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unable to find group with id {group_id}",
            )
        return group

    def get_group_by_name(self, group_name: str) -> Group | None:
        """Get group by name."""
        return self.db.query(Group).filter(Group.name_uniform == group_name.lower()).first()

    def get_group_join_date(self, user_id: int, group_id: int) -> datetime | None:
        """Get user join date."""
        stmt = select(group_members.c.joined_at).where(
            group_members.c.group_id == group_id, group_members.c.user_id == user_id
        )
        return self.db.execute(stmt).scalar()

    def get_user_role(self, user_id: int, group_id: int) -> GroupRole | None:
        stmt = select(group_members.c.role).where(
            group_members.c.user_id == user_id, group_members.c.group_id == group_id
        )
        role = self.db.execute(stmt).scalar()
        if role is not None:
            return GroupRole(role)
        return None

    def get_users_with_role(self, group_id: int, role: GroupRole) -> list[int]:
        stmt = select(group_members.c.user_id).where(
            group_members.c.group_id == group_id,
            group_members.c.role == role.value,
        )
        return list(self.db.execute(stmt).scalars().all())

    # ==================== ROLE MGMT ====================

    def is_admin(self, user_id: int, group_id: int) -> bool:
        """Is the user a group admin."""
        return self.get_user_role(user_id, group_id) == GroupRole.Admin

    def is_owner(self, user_id: int, group_id: int) -> bool:
        """Is the user the group owner."""
        return self.get_user_role(user_id, group_id) == GroupRole.Owner

    def is_admin_or_owner(self, user_id: int, group_id: int) -> bool:
        """Is the user a group admin or owner."""
        return self.is_owner(user_id, group_id) or self.is_admin(user_id, group_id)

    def set_user_role(
        self,
        user_id: int,
        set_by_user_id: int,
        group_id: int,
        role: GroupRole,
        *,
        force: bool = False,
    ):
        """Set the user role within a group

        Args:
            user_id (int): User ID whose role is to be changed.
            set_by_user_id (int): User ID who initiated the change of role.
            group_id (int): Group ID for which to reflect the change.
            role (GroupRole): Desired role for user_id.
            force (optional, bool): Whether to bypass the role req. check on set_by_user_id and force the change.
                Defaults to False.

        Raises:
            HTTPException 403: If force=False and set_by_user_id is not an admin or owner.
            HTTPException 404: If the user_id is not in the group.
        """
        if not force:
            self.require_membership(set_by_user_id, group_id)
        self.require_membership(user_id, group_id)

        if not force:
            self.require_permission(set_by_user_id, group_id, role)

        try:
            stmt = (
                update(group_members)
                .where(group_members.c.user_id == user_id, group_members.c.group_id == group_id)
                .values(role=role.value)
            )
            self.db.execute(stmt)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update user role due to existing dependencies",
            ) from None


    # ==================== HELPERS ====================
    def require_permission(self, user_id: int, group_id: int, min_role: GroupRole):
        """
        Require user to have at least the specified role.
        
        Raises:
            HTTPException 403: If user doesn't have sufficient permissions
        """
        user_role = self.get_user_role(user_id, group_id)
        if user_role is None or user_role > min_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least {min_role.value} role"
            )
    
    def require_membership(self, user_id: int, group_id: int) -> None:
        """
        Require user to be a member of the group.
        
        Raises:
            HTTPException 403: If user is not a member
        """
        if not self.is_user_in_group(user_id, group_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be a member of this group"
            )

    # ==================== MUTATION ====================
    def update_group_settings(
        self, group_id: int, modified_by_user_id: int, update_data: GroupModifyRequest
    ):
        self.require_permission(modified_by_user_id, group_id, GroupRole.Admin)
        group = self.get_group_by_id(group_id)

        # Change name
        if update_data.name is not None:
            self._update_group_name(group, update_data.name)

        # Change visibility
        if update_data.is_public is not None:
            group.is_public = update_data.is_public

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update group name due to existing dependencies.",
            ) from None

    def _update_group_name(self, group: Group, name: str):
        """Update the group name."""
        existing_group = self.get_group_by_name(name)
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Group name already registered"
            )

        group.name = name

    # ==================== SEARCH ====================

    def search_groups(
        self, query: str | None = None, username: str | None = None, limit: int = 10
    ) -> list[Group]:
        """Search public groups by partial name and/or member username."""
        q = self.db.query(Group).filter(Group.is_public == True)  # noqa: E712
        if query:
            q = q.filter(Group.name_uniform.contains(query.lower()))
        if username:
            q = q.join(Group.members).filter(func.lower(User.username) == username.lower())
        return q.limit(limit).all()

    # ==================== STATS ====================

    def get_group_stats(self, group_id: int) -> dict:
        """Return aggregate statistics for a group.

        Raises:
            HTTPException 404: If group not found.
        """
        group = self.get_group_by_id(group_id)
        albums_reviewed = sum(1 for a in group.albums if a.status == "reviewed")
        return {
            "member_count": len(group.members),
            "albums_added": len(group.albums),
            "albums_reviewed": albums_reviewed,
            "formed_at": group.created_at,
        }

    # ==================== MEMBERS ====================

    def get_group_members(self, group_id: int) -> list[dict]:
        """Return members of a group with their role and join date."""
        stmt = (
            select(
                group_members.c.user_id,
                User.username,
                group_members.c.role,
                group_members.c.joined_at,
            )
            .join(User, group_members.c.user_id == User.id)
            .where(group_members.c.group_id == group_id)
        )
        rows = self.db.execute(stmt).all()
        return [
            {"user_id": r.user_id, "username": r.username, "role": r.role, "joined_at": r.joined_at}
            for r in rows
        ]

    # ==================== UTILS ====================
    def is_user_in_group(self, user_id: int, group_id: int) -> bool:
        """Determine whether a given user is in a group."""
        stmt = select(group_members).where(
            group_members.c.group_id == group_id, group_members.c.user_id == user_id
        )
        result = self.db.execute(stmt).first()
        return result is not None
