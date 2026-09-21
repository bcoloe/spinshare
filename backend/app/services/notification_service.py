"""Notification service."""

from collections.abc import Sequence
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import User
from app.models.notification import Notification
from app.schemas.notification import NotificationType

_MAX_UNREAD = 200


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create(
        self,
        user_id: int,
        type: NotificationType,
        message: str,
        group_id: int | None = None,
        album_id: int | None = None,
    ) -> Notification:
        """Create a notification for a user."""
        notification = Notification(
            user_id=user_id,
            type=type,
            message=message,
            group_id=group_id,
            album_id=album_id,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def create_many(
        self,
        user_ids: Sequence[int],
        type: NotificationType,
        message: str,
        group_id: int | None = None,
        album_id: int | None = None,
    ) -> int:
        """Create the same notification for many users in one transaction.

        ``create`` commits per call, so fanning out to N recipients that way costs
        N round trips. Every notification with more than one recipient is identical
        apart from ``user_id``, so they can all go in a single insert + commit.

        Returns the number of notifications created.
        """
        if not user_ids:
            return 0

        self.db.add_all([
            Notification(
                user_id=user_id,
                type=type,
                message=message,
                group_id=group_id,
                album_id=album_id,
            )
            for user_id in user_ids
        ])
        self.db.commit()
        return len(user_ids)

    # ==================== READ ====================

    def get_unread(self, user: User) -> list[Notification]:
        """Return a user's unread notifications, newest first.

        Capped at ``_MAX_UNREAD`` rows. The endpoint returns a bare list and so
        cannot grow an offset/limit contract without changing its response
        shape, and a user who never clears the bell should not be able to make
        the request unbounded. The cap keeps the newest, which is what the badge
        and dropdown actually show.
        """
        return list(
            self.db.scalars(
                select(Notification)
                .where(
                    Notification.user_id == user.id,
                    Notification.read_at.is_(None),
                )
                .order_by(Notification.created_at.desc())
                .limit(_MAX_UNREAD)
            ).all()
        )

    def get_all(self, user: User, limit: int = 50) -> list[Notification]:
        """Return all notifications for a user, newest first."""
        return list(
            self.db.scalars(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            ).all()
        )

    # ==================== UPDATE ====================

    def mark_read(self, notification_id: int, user: User) -> Notification:
        """Mark a single notification as read.

        Raises:
            HTTPException 404: If not found or does not belong to this user
        """
        notification = self.db.scalars(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user.id,
            )
        ).first()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        notification.read_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_read_for_group(self, user: User, group_id: int, type: NotificationType) -> int:
        """Mark this user's unread notifications of one type in one group as read.

        Backs "reading the thing clears the badge" flows, where the UI that shows
        the underlying activity can retire its own notifications instead of
        making the user dismiss them one by one. Scoped to a single type so, say,
        watching chat never silently clears an unrelated review notification.

        Issued as a single UPDATE rather than a select-then-loop: this runs on a
        UI signal (a panel opening, a message arriving) rather than a user
        action, so it should cost one round trip no matter how many rows match.

        Returns:
            The number of notifications that were still unread and got marked.
        """
        result = self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.group_id == group_id,
                Notification.type == type.value,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        self.db.commit()
        return result.rowcount

    def mark_all_read(self, user: User) -> None:
        """Mark all unread notifications for a user as read.

        One UPDATE, for the same reason as ``mark_read_for_group``: the cost
        must not scale with a backlog the user never looked at.
        """
        self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        self.db.commit()
