"""Tests for NotificationService."""

import pytest
from fastapi import HTTPException, status

from app.models.notification import Notification
from app.schemas.notification import NotificationType
from app.services.notification_service import NotificationService


@pytest.fixture
def notification_service(db_session):
    return NotificationService(db_session)


def _make_notification(db_session, *, user_id, read=False):
    from datetime import datetime, timezone
    n = Notification(
        user_id=user_id,
        type=NotificationType.invitation_accepted,
        message="alice accepted your invitation",
        read_at=datetime.now(timezone.utc) if read else None,
    )
    db_session.add(n)
    db_session.commit()
    db_session.refresh(n)
    return n


class TestCreateNotification:
    def test_create_success(self, notification_service, sample_user):
        n = notification_service.create(
            user_id=sample_user.id,
            type=NotificationType.invitation_accepted,
            message="test message",
            group_id=None,
        )
        assert n.id is not None
        assert n.message == "test message"
        assert n.read_at is None

    def test_create_with_group(self, notification_service, sample_user, sample_group):
        n = notification_service.create(
            user_id=sample_user.id,
            type=NotificationType.invitation_declined,
            message="test",
            group_id=sample_group.id,
        )
        assert n.group_id == sample_group.id


class TestGetUnread:
    def test_returns_only_unread(self, db_session, notification_service, sample_user):
        _make_notification(db_session, user_id=sample_user.id)
        _make_notification(db_session, user_id=sample_user.id, read=True)

        results = notification_service.get_unread(sample_user)
        assert len(results) == 1
        assert results[0].read_at is None

    def test_excludes_other_users(self, db_session, notification_service, sample_user, user_factory):
        other = user_factory(email="other@test.com", username="other")
        _make_notification(db_session, user_id=other.id)

        assert notification_service.get_unread(sample_user) == []


class TestMarkRead:
    def test_mark_read_success(self, db_session, notification_service, sample_user):
        n = _make_notification(db_session, user_id=sample_user.id)
        updated = notification_service.mark_read(n.id, sample_user)
        assert updated.read_at is not None

    def test_mark_read_wrong_user_raises_404(self, db_session, notification_service, sample_user, user_factory):
        other = user_factory(email="other@test.com", username="other")
        n = _make_notification(db_session, user_id=other.id)

        with pytest.raises(HTTPException) as exc_info:
            notification_service.mark_read(n.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_mark_read_not_found_raises_404(self, notification_service, sample_user):
        with pytest.raises(HTTPException) as exc_info:
            notification_service.mark_read(9999, sample_user)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestGetAll:
    def test_returns_all_notifications(self, db_session, notification_service, sample_user):
        _make_notification(db_session, user_id=sample_user.id)
        _make_notification(db_session, user_id=sample_user.id, read=True)

        results = notification_service.get_all(sample_user)
        assert len(results) == 2

    def test_excludes_other_users(self, db_session, notification_service, sample_user, user_factory):
        other = user_factory(email="other@test.com", username="other")
        _make_notification(db_session, user_id=other.id)

        assert notification_service.get_all(sample_user) == []

    def test_respects_limit(self, db_session, notification_service, sample_user):
        for _ in range(5):
            _make_notification(db_session, user_id=sample_user.id)

        results = notification_service.get_all(sample_user, limit=3)
        assert len(results) == 3

    def test_ordered_newest_first(self, db_session, notification_service, sample_user):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        older = Notification(
            user_id=sample_user.id,
            type=NotificationType.invitation_accepted,
            message="older",
            created_at=now - timedelta(hours=1),
        )
        newer = Notification(
            user_id=sample_user.id,
            type=NotificationType.invitation_accepted,
            message="newer",
            created_at=now,
        )
        db_session.add_all([older, newer])
        db_session.commit()

        results = notification_service.get_all(sample_user)
        assert results[0].message == "newer"
        assert results[1].message == "older"


class TestMarkAllRead:
    def test_marks_all_unread(self, db_session, notification_service, sample_user):
        _make_notification(db_session, user_id=sample_user.id)
        _make_notification(db_session, user_id=sample_user.id)

        notification_service.mark_all_read(sample_user)
        assert notification_service.get_unread(sample_user) == []

    def test_does_not_affect_other_users(self, db_session, notification_service, sample_user, user_factory):
        other = user_factory(email="other@test.com", username="other")
        _make_notification(db_session, user_id=other.id)

        notification_service.mark_all_read(sample_user)

        other_unread = notification_service.get_unread(other)
        assert len(other_unread) == 1
