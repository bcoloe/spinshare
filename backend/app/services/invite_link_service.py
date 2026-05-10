"""Invite link service."""

import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.models.group import GroupRole
from app.models.invite_link import GroupInviteLink
from app.services.group_service import GroupService


class InviteLinkService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== READ ====================

    def get_link(
        self, group_id: int, requester: User, group_service: GroupService
    ) -> GroupInviteLink | None:
        """Return the active invite link for a group, or None if none exists.

        Raises:
            HTTPException 403: If requester is not Admin or Owner
            HTTPException 404: If group not found
        """
        group_service.get_group_by_id(group_id)
        group_service.require_permission(requester.id, group_id, GroupRole.Admin)
        return self._get_link_for_group(group_id)

    def get_link_by_token(self, token: str) -> GroupInviteLink:
        """Public lookup by token.

        Raises:
            HTTPException 404: If token not found
        """
        link = self.db.scalars(
            select(GroupInviteLink).where(GroupInviteLink.token == token)
        ).first()
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite link not found",
            )
        return link

    # ==================== CREATE / ROTATE ====================

    def create_or_rotate_link(
        self, group_id: int, requester: User, group_service: GroupService
    ) -> GroupInviteLink:
        """Create a new invite link, or rotate the token if one already exists.

        Raises:
            HTTPException 403: If requester is not Admin or Owner
            HTTPException 404: If group not found
        """
        group_service.get_group_by_id(group_id)
        group_service.require_permission(requester.id, group_id, GroupRole.Admin)

        link = self._get_link_for_group(group_id)
        if link:
            link.token = secrets.token_urlsafe(32)
            link.created_by = requester.id
        else:
            link = GroupInviteLink(
                group_id=group_id,
                created_by=requester.id,
                token=secrets.token_urlsafe(32),
            )
            self.db.add(link)

        self.db.commit()
        self.db.refresh(link)
        return link

    # ==================== DELETE ====================

    def revoke_link(
        self, group_id: int, requester: User, group_service: GroupService
    ) -> None:
        """Revoke (delete) the invite link for a group.

        Raises:
            HTTPException 403: If requester is not Admin or Owner
            HTTPException 404: If group or link not found
        """
        group_service.get_group_by_id(group_id)
        group_service.require_permission(requester.id, group_id, GroupRole.Admin)

        link = self._get_link_for_group(group_id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active invite link for this group",
            )
        self.db.delete(link)
        self.db.commit()

    # ==================== ACCEPT ====================

    def accept_link(
        self, token: str, user: User, group_service: GroupService
    ) -> GroupInviteLink:
        """Join a group via an invite link.

        Raises:
            HTTPException 404: If token not found
            HTTPException 409: If user is already a member
        """
        link = self.get_link_by_token(token)

        if group_service.is_user_in_group(user.id, link.group_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already a member of this group",
            )

        group_service.add_user(link.group_id, user.id)
        self.db.refresh(link)
        return link

    # ==================== PRIVATE ====================

    def _get_link_for_group(self, group_id: int) -> GroupInviteLink | None:
        return self.db.scalars(
            select(GroupInviteLink).where(GroupInviteLink.group_id == group_id)
        ).first()
