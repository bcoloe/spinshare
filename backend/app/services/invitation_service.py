"""Invitation service."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Group, User
from app.models.group import GroupRole
from app.models.invitation import GroupInvitation
from app.schemas.invitation import InvitationCreate
from app.schemas.notification import NotificationType
from app.services.group_service import GroupService
from app.services.notification_service import NotificationService
from app.utils.email import send_invitation_email

_INVITATION_TTL_DAYS = 7


class InvitationService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create_invitation(
        self,
        group_id: int,
        data: InvitationCreate,
        inviter: User,
        group_service: GroupService,
    ) -> GroupInvitation:
        """Create and send a group invitation email.

        Raises:
            HTTPException 403: If inviter is not Admin or Owner
            HTTPException 404: If group not found
            HTTPException 409: If email already has a pending invitation or is already a member
        """
        group = group_service.get_group_by_id(group_id)
        group_service.require_permission(inviter.id, group_id, GroupRole.Admin)

        email = data.email.lower()

        existing_user = self.db.scalars(select(User).where(User.email == email)).first()
        if existing_user and group_service.is_user_in_group(existing_user.id, group_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this group",
            )

        if self._get_pending_invitation(group_id, email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pending invitation already exists for this email",
            )

        now = datetime.now(timezone.utc)
        invitation = GroupInvitation(
            group_id=group_id,
            invited_email=email,
            invited_by=inviter.id,
            token=secrets.token_urlsafe(32),
            expires_at=now + timedelta(days=_INVITATION_TTL_DAYS),
        )
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)

        settings = get_settings()
        invite_url = f"{settings.FRONTEND_URL}/invite/{invitation.token}"
        send_invitation_email(
            to_email=email,
            group_name=group.name,
            inviter_username=inviter.username,
            invite_url=invite_url,
        )

        return invitation

    # ==================== READ ====================

    def get_invitation_by_token(self, token: str) -> GroupInvitation:
        """Get an invitation by its token.

        Raises:
            HTTPException 404: If not found
        """
        invitation = self.db.scalars(
            select(GroupInvitation).where(GroupInvitation.token == token)
        ).first()
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )
        return invitation

    def get_group_invitations(
        self, group_id: int, requester: User, group_service: GroupService
    ) -> list[GroupInvitation]:
        """List all pending (non-accepted) invitations for a group.

        Raises:
            HTTPException 403: If requester is not Admin or Owner
            HTTPException 404: If group not found
        """
        group_service.get_group_by_id(group_id)
        group_service.require_permission(requester.id, group_id, GroupRole.Admin)
        return list(
            self.db.scalars(
                select(GroupInvitation)
                .where(
                    GroupInvitation.group_id == group_id,
                    GroupInvitation.accepted_at.is_(None),
                )
                .order_by(GroupInvitation.created_at.desc())
            ).all()
        )

    # ==================== UPDATE ====================

    def accept_invitation(
        self, token: str, user: User, group_service: GroupService
    ) -> GroupInvitation:
        """Accept a group invitation.

        Raises:
            HTTPException 403: If user's email doesn't match the invitation
            HTTPException 404: If invitation not found
            HTTPException 409: If user is already a group member
            HTTPException 410: If invitation is expired or already accepted
        """
        invitation = self.get_invitation_by_token(token)
        now = datetime.now(timezone.utc)

        if invitation.accepted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invitation has already been accepted",
            )
        if invitation.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invitation has expired",
            )
        if user.email.lower() != invitation.invited_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This invitation was sent to a different email address",
            )

        group_service.add_user(invitation.group_id, user.id)

        invitation.accepted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(invitation)

        NotificationService(self.db).create(
            user_id=invitation.invited_by,
            type=NotificationType.invitation_accepted,
            message=f"{user.username} accepted your invitation to join {invitation.group_name}",
            group_id=invitation.group_id,
        )

        return invitation

    def get_user_pending_invitations(self, user: User) -> list[GroupInvitation]:
        """Return all pending, non-expired invitations addressed to this user."""
        now = datetime.now(timezone.utc)
        return list(
            self.db.scalars(
                select(GroupInvitation)
                .where(
                    GroupInvitation.invited_email == user.email.lower(),
                    GroupInvitation.accepted_at.is_(None),
                    GroupInvitation.expires_at > now,
                )
                .order_by(GroupInvitation.created_at.desc())
            ).all()
        )

    # ==================== DELETE ====================

    def revoke_invitation(
        self,
        invitation_id: int,
        requester: User,
        group_service: GroupService,
    ) -> None:
        """Revoke a pending invitation.

        Raises:
            HTTPException 404: If not found
            HTTPException 403: If requester is not Admin or Owner
            HTTPException 409: If invitation has already been accepted
        """
        invitation = self.db.get(GroupInvitation, invitation_id)
        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found",
            )

        group_service.require_permission(requester.id, invitation.group_id, GroupRole.Admin)

        if invitation.accepted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot revoke an already-accepted invitation",
            )

        self.db.delete(invitation)
        self.db.commit()

    def decline_invitation(self, token: str, user: User) -> None:
        """Decline a pending invitation addressed to this user.

        Raises:
            HTTPException 403: If invitation is not addressed to this user
            HTTPException 404: If invitation not found
            HTTPException 410: If invitation is expired or already accepted
        """
        invitation = self.get_invitation_by_token(token)
        now = datetime.now(timezone.utc)

        if invitation.accepted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invitation has already been accepted",
            )
        if invitation.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invitation has expired",
            )
        if user.email.lower() != invitation.invited_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This invitation was not sent to your account",
            )

        inviter_id = invitation.invited_by
        group_id = invitation.group_id
        group_name = invitation.group_name

        self.db.delete(invitation)
        self.db.commit()

        NotificationService(self.db).create(
            user_id=inviter_id,
            type=NotificationType.invitation_declined,
            message=f"{user.username} declined your invitation to join {group_name}",
            group_id=group_id,
        )

    # ==================== PRIVATE ====================

    def _get_pending_invitation(self, group_id: int, email: str) -> GroupInvitation | None:
        now = datetime.now(timezone.utc)
        return self.db.scalars(
            select(GroupInvitation).where(
                GroupInvitation.group_id == group_id,
                GroupInvitation.invited_email == email,
                GroupInvitation.accepted_at.is_(None),
                GroupInvitation.expires_at > now,
            )
        ).first()
