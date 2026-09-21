from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from app.models import GroupAlbum
from app.models.notification import Notification
from app.schemas.album import ReviewCreate, ReviewUpdate
from app.schemas.notification import NotificationType
from app.services.notification_service import NotificationService
from fastapi import HTTPException, status
from sqlalchemy import event


class TestReviewServiceCreate:
    def test_create_review_success(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=8.5, comment="Great album")
        review = review_service.create_review(sample_album.id, sample_user.id, data)

        assert review.id is not None
        assert review.album_id == sample_album.id
        assert review.user_id == sample_user.id
        assert review.rating == 8.5
        assert review.comment == "Great album"
        assert review.is_draft is False
        assert review.reviewed_at is not None

    def test_create_review_no_comment(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=7.0)
        review = review_service.create_review(sample_album.id, sample_user.id, data)
        assert review.comment is None

    def test_create_review_as_draft(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=6.0, is_draft=True)
        review = review_service.create_review(sample_album.id, sample_user.id, data)
        assert review.is_draft is True

    def test_create_draft_without_rating(self, review_service, sample_album, sample_user):
        data = ReviewCreate(is_draft=True)
        review = review_service.create_review(sample_album.id, sample_user.id, data)
        assert review.is_draft is True
        assert review.rating is None

    def test_create_published_review_requires_rating(self):
        with pytest.raises(ValueError, match="rating is required"):
            ReviewCreate(is_draft=False)

    def test_create_review_duplicate_conflict(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=5.0)
        review_service.create_review(sample_album.id, sample_user.id, data)
        with pytest.raises(HTTPException) as exc_info:
            review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=6.0))
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_create_review_is_first_review_true(
        self, review_service, sample_album, sample_user, sample_group
    ):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=8.0), group_id=sample_group.id
        )
        assert review.is_first_review is True

    def test_create_review_is_first_review_false_when_group_member_already_reviewed(
        self, db_session, review_service, sample_album, sample_user, sample_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        sample_group.members.append(other)
        db_session.commit()
        review_service.create_review(
            sample_album.id, other.id, ReviewCreate(rating=6.0), group_id=sample_group.id
        )

        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=8.0), group_id=sample_group.id
        )
        assert review.is_first_review is False

    def test_create_review_is_first_review_false_without_group_id(
        self, review_service, sample_album, sample_user
    ):
        review = review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=8.0))
        assert review.is_first_review is False

    def test_create_draft_review_is_not_first_review(
        self, review_service, sample_album, sample_user, sample_group
    ):
        review = review_service.create_review(
            sample_album.id,
            sample_user.id,
            ReviewCreate(rating=8.0, is_draft=True),
            group_id=sample_group.id,
        )
        assert review.is_first_review is False


class TestReviewServiceGet:
    def test_get_review_by_id_success(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=9.0)
        created = review_service.create_review(sample_album.id, sample_user.id, data)
        fetched = review_service.get_review_by_id(created.id)
        assert fetched.id == created.id

    def test_get_review_by_id_not_found(self, review_service):
        with pytest.raises(HTTPException) as exc_info:
            review_service.get_review_by_id(99999)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_reviews_for_album(self, review_service, sample_album, sample_user, user_factory):
        other = user_factory(email="other@test.com", username="other_reviewer")
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        reviews = review_service.get_reviews_for_album(sample_album.id)
        assert len(reviews) == 2
        usernames = {r.username for r in reviews}
        assert "test_user" in usernames
        assert "other_reviewer" in usernames

    def test_get_reviews_for_album_excludes_drafts(
        self, review_service, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(
            sample_album.id, other.id, ReviewCreate(rating=8.0, is_draft=True)
        )

        reviews = review_service.get_reviews_for_album(sample_album.id)
        assert len(reviews) == 1
        assert reviews[0].user_id == sample_user.id
        assert reviews[0].username == "test_user"

    def test_get_reviews_for_album_empty(self, review_service, sample_album):
        reviews = review_service.get_reviews_for_album(sample_album.id)
        assert reviews == []

    def test_get_review_by_user_and_album_success(self, review_service, sample_album, sample_user):
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=6.0))
        result = review_service.get_review_by_user_and_album(sample_album.id, sample_user.id)
        assert result.user_id == sample_user.id
        assert result.album_id == sample_album.id

    def test_get_review_by_user_and_album_not_found_raises(
        self, review_service, sample_album, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            review_service.get_review_by_user_and_album(sample_album.id, sample_user.id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_review_by_user_and_album_not_found_silent(
        self, review_service, sample_album, sample_user
    ):
        result = review_service.get_review_by_user_and_album(
            sample_album.id, sample_user.id, raise_on_missing=False
        )
        assert result is None


class TestReviewServiceUpdate:
    def test_update_review_rating(self, review_service, sample_album, sample_user):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=5.0)
        )
        updated = review_service.update_review(review.id, sample_user.id, ReviewUpdate(rating=9.5))
        assert updated.rating == 9.5

    def test_update_review_comment(self, review_service, sample_album, sample_user):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0, comment="OK")
        )
        updated = review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(comment="Amazing")
        )
        assert updated.comment == "Amazing"
        assert updated.rating == 7.0

    def test_update_review_wrong_user_forbidden(
        self, review_service, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_user")
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0)
        )
        with pytest.raises(HTTPException) as exc_info:
            review_service.update_review(review.id, other.id, ReviewUpdate(rating=1.0))
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_update_draft_to_published(self, review_service, sample_album, sample_user):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0, is_draft=True)
        )
        assert review.is_draft is True

        updated = review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(is_draft=False)
        )
        assert updated.is_draft is False

    def test_update_draft_save_keeps_draft(self, review_service, sample_album, sample_user):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0, is_draft=True)
        )
        updated = review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(rating=9.0, is_draft=True)
        )
        assert updated.is_draft is True
        assert updated.rating == 9.0

    def test_submit_draft_without_rating_raises(self, review_service, sample_album, sample_user):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(is_draft=True)
        )
        with pytest.raises(HTTPException) as exc_info:
            review_service.update_review(review.id, sample_user.id, ReviewUpdate(is_draft=False))
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_publish_draft_is_first_review_true(
        self, review_service, sample_album, sample_user, sample_group
    ):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0, is_draft=True)
        )
        updated = review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(is_draft=False), group_id=sample_group.id
        )
        assert updated.is_first_review is True

    def test_publish_draft_is_first_review_false_when_group_member_already_reviewed(
        self, db_session, review_service, sample_album, sample_user, sample_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        sample_group.members.append(other)
        db_session.commit()
        review_service.create_review(
            sample_album.id, other.id, ReviewCreate(rating=6.0), group_id=sample_group.id
        )

        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0, is_draft=True)
        )
        updated = review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(is_draft=False), group_id=sample_group.id
        )
        assert updated.is_first_review is False

    def test_edit_already_published_review_is_not_first_review(
        self, review_service, sample_album, sample_user, sample_group
    ):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0), group_id=sample_group.id
        )
        updated = review_service.update_review(
            review.id, sample_user.id, ReviewUpdate(rating=9.0), group_id=sample_group.id
        )
        assert updated.is_first_review is False


class TestReviewServiceDelete:
    def test_delete_review_success(self, review_service, sample_album, sample_user):
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=8.0)
        )
        review_service.delete_review(review.id, sample_user.id)
        with pytest.raises(HTTPException):
            review_service.get_review_by_id(review.id)

    def test_delete_review_wrong_user_forbidden(
        self, review_service, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_deleter")
        review = review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=8.0)
        )
        with pytest.raises(HTTPException) as exc_info:
            review_service.delete_review(review.id, other.id)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestReviewNotifications:
    def _link_album_to_group(self, db_session, group_id, album_id, added_by_id):
        ga = GroupAlbum(group_id=group_id, album_id=album_id, added_by=added_by_id)
        db_session.add(ga)
        db_session.commit()

    def test_notifies_co_reviewer_in_same_group(
        self, db_session, review_service, sample_album, sample_user, sample_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        sample_group.members.append(other)
        db_session.commit()
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        ns = NotificationService(db_session)
        unread = ns.get_unread(sample_user)
        assert len(unread) == 1
        assert unread[0].type == NotificationType.member_reviewed_album
        assert unread[0].group_id == sample_group.id
        assert unread[0].album_id == sample_album.id
        assert "other_reviewer" in unread[0].message

    def test_notification_carries_album_id(
        self, db_session, review_service, sample_album, sample_user, sample_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        sample_group.members.append(other)
        db_session.commit()
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        ns = NotificationService(db_session)
        unread = ns.get_unread(sample_user)
        assert unread[0].album_id == sample_album.id

    def test_no_notification_when_no_prior_reviewers(
        self, db_session, review_service, sample_album, sample_user, sample_group
    ):
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))

        ns = NotificationService(db_session)
        assert ns.get_unread(sample_user) == []

    def test_no_notification_for_global_group(
        self, db_session, review_service, sample_album, sample_user, global_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        global_group.members.append(sample_user)
        global_group.members.append(other)
        db_session.commit()
        self._link_album_to_group(db_session, global_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        ns = NotificationService(db_session)
        assert ns.get_unread(sample_user) == []

    def test_reviewer_does_not_notify_themselves(
        self, db_session, review_service, sample_album, sample_user, sample_group
    ):
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))

        ns = NotificationService(db_session)
        assert ns.get_unread(sample_user) == []

    def test_draft_create_does_not_notify(
        self, db_session, review_service, sample_album, sample_user, sample_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        sample_group.members.append(other)
        db_session.commit()
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(
            sample_album.id, other.id, ReviewCreate(rating=8.0, is_draft=True)
        )

        ns = NotificationService(db_session)
        assert ns.get_unread(sample_user) == []

    def test_draft_publish_notifies_co_reviewers(
        self, db_session, review_service, sample_album, sample_user, sample_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        sample_group.members.append(other)
        db_session.commit()
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        draft = review_service.create_review(
            sample_album.id, other.id, ReviewCreate(rating=8.0, is_draft=True)
        )

        review_service.update_review(draft.id, other.id, ReviewUpdate(is_draft=False))

        ns = NotificationService(db_session)
        unread = ns.get_unread(sample_user)
        assert len(unread) == 1
        assert unread[0].type == NotificationType.member_reviewed_album

    def test_draft_co_reviewer_not_notified_when_others_publish(
        self, db_session, review_service, sample_album, sample_user, sample_group, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        sample_group.members.append(other)
        db_session.commit()
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(
            sample_album.id, sample_user.id, ReviewCreate(rating=7.0, is_draft=True)
        )
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        ns = NotificationService(db_session)
        assert ns.get_unread(sample_user) == []

    def test_no_duplicate_notification_when_album_in_multiple_shared_groups(
        self, db_session, review_service, sample_album, sample_user, sample_group, group_factory, user_factory
    ):
        """Co-reviewer gets exactly one notification even when both users share multiple groups."""
        other = user_factory(email="other@test.com", username="other_reviewer")
        second_group = group_factory(name="Second Group")
        second_group.members.append(other)
        db_session.commit()
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)
        self._link_album_to_group(db_session, second_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        ns = NotificationService(db_session)
        unread = ns.get_unread(sample_user)
        assert len(unread) == 1
        assert unread[0].type == NotificationType.member_reviewed_album

    def test_notification_scoped_to_reviewers_shared_group(
        self, db_session, review_service, sample_album, sample_user, sample_group, group_factory, user_factory
    ):
        """Notification group_id is the group where the new reviewer is a member, not others."""
        other = user_factory(email="other@test.com", username="other_reviewer")
        # other is only in sample_group, not second_group
        sample_group.members.append(other)
        second_group = group_factory(name="Second Group")
        db_session.commit()
        self._link_album_to_group(db_session, sample_group.id, sample_album.id, sample_user.id)
        self._link_album_to_group(db_session, second_group.id, sample_album.id, sample_user.id)

        # sample_user reviews first (is in both groups), then other reviews (only in sample_group)
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        ns = NotificationService(db_session)
        unread = ns.get_unread(sample_user)
        assert len(unread) == 1
        assert unread[0].group_id == sample_group.id


def _selected_ga(db_session, group_id, album_id, added_by) -> GroupAlbum:
    """Insert a GroupAlbum with selected_date so status-filter queries include it."""
    ga = GroupAlbum(
        group_id=group_id,
        album_id=album_id,
        added_by=added_by,
        selected_date=datetime.now(tz=timezone.utc),
    )
    db_session.add(ga)
    db_session.commit()
    db_session.refresh(ga)
    return ga


class TestGroupReviews:
    def test_get_my_reviews_for_group_returns_own_reviews(
        self, db_session, review_service, sample_group, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_user")
        _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        results = review_service.get_my_reviews_for_group(sample_group.id, sample_user.id)
        assert len(results) == 1
        assert results[0].user_id == sample_user.id
        assert results[0].album_id == sample_album.id

    def test_get_my_reviews_for_group_excludes_pending_albums(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        db_session.add(ga)
        db_session.commit()

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))

        results = review_service.get_my_reviews_for_group(sample_group.id, sample_user.id)
        assert results == []

    def test_get_my_reviews_for_group_includes_drafts(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=6.0, is_draft=True))

        results = review_service.get_my_reviews_for_group(sample_group.id, sample_user.id)
        assert len(results) == 1
        assert results[0].is_draft is True

    def test_get_my_reviews_for_group_empty_when_no_albums(
        self, review_service, sample_group, sample_user
    ):
        results = review_service.get_my_reviews_for_group(sample_group.id, sample_user.id)
        assert results == []

    def test_get_my_reviews_for_group_empty_when_no_reviews(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        results = review_service.get_my_reviews_for_group(sample_group.id, sample_user.id)
        assert results == []

    def test_get_all_reviews_for_group_returns_published(
        self, db_session, review_service, sample_group, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_user")
        _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0))

        results = review_service.get_all_reviews_for_group(sample_group.id, sample_user.id)
        assert len(results) == 2

    def test_get_all_reviews_for_group_excludes_pending_albums(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        db_session.add(ga)
        db_session.commit()

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))

        results = review_service.get_all_reviews_for_group(sample_group.id, sample_user.id)
        assert results == []

    def test_get_all_reviews_for_group_excludes_drafts(
        self, db_session, review_service, sample_group, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_user")
        _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=8.0, is_draft=True))

        results = review_service.get_all_reviews_for_group(sample_group.id, sample_user.id)
        assert len(results) == 1
        assert results[0].user_id == sample_user.id

    def test_get_all_reviews_for_group_empty_when_no_albums(
        self, review_service, sample_group, sample_user
    ):
        results = review_service.get_all_reviews_for_group(sample_group.id, sample_user.id)
        assert results == []


class TestGroupAlbumAvgCache:
    def test_create_review_updates_avg_rating(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        ga = _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=8.0))

        db_session.refresh(ga)
        assert ga.avg_rating == 8.0
        assert ga.review_count == 1

    def test_avg_counts_only_group_members(
        self, db_session, review_service, sample_group, sample_album, sample_user, user_factory
    ):
        non_member = user_factory(email="outsider@test.com", username="outsider")
        ga = _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=6.0))
        review_service.create_review(sample_album.id, non_member.id, ReviewCreate(rating=10.0))

        db_session.refresh(ga)
        assert ga.avg_rating == 6.0
        assert ga.review_count == 1

    def test_avg_excludes_drafts(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        ga = _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.0, is_draft=True))

        db_session.refresh(ga)
        assert ga.avg_rating is None
        assert ga.review_count == 0

    def test_update_review_refreshes_avg(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        ga = _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)
        review = review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=6.0))

        review_service.update_review(review.id, sample_user.id, ReviewUpdate(rating=9.0))

        db_session.refresh(ga)
        assert ga.avg_rating == 9.0

    def test_delete_review_refreshes_avg(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        ga = _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)
        review = review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=8.0))

        review_service.delete_review(review.id, sample_user.id)

        db_session.refresh(ga)
        assert ga.avg_rating is None
        assert ga.review_count == 0

    def test_avg_is_none_when_no_rated_reviews(
        self, db_session, review_service, sample_group, sample_album, sample_user
    ):
        ga = _selected_ga(db_session, sample_group.id, sample_album.id, sample_user.id)

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=None, is_draft=True))

        db_session.refresh(ga)
        assert ga.avg_rating is None
        assert ga.review_count == 0


class TestAlbumStats:
    def test_empty_album_returns_zero_histogram(self, review_service, sample_album):
        stats = review_service.get_album_stats(sample_album.id)
        assert stats.average_rating is None
        assert stats.rating_stddev is None
        assert stats.review_count == 0
        assert len(stats.histogram) == 10
        assert all(b.count == 0 for b in stats.histogram)

    def test_histogram_bucket_labels(self, review_service, sample_album):
        stats = review_service.get_album_stats(sample_album.id)
        for i, bucket in enumerate(stats.histogram):
            assert bucket.bucket_start == i
            assert bucket.bucket_end == i + 1

    def test_single_review_average_and_bucket(self, review_service, sample_album, sample_user):
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=7.5))
        stats = review_service.get_album_stats(sample_album.id)
        assert stats.average_rating == 7.5
        assert stats.rating_stddev == 0.0  # single rating → no spread
        assert stats.review_count == 1
        assert stats.histogram[7].count == 1
        assert sum(b.count for b in stats.histogram) == 1

    def test_multiple_reviews_span_buckets(
        self, review_service, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_reviewer")
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=3.0))
        review_service.create_review(sample_album.id, other.id, ReviewCreate(rating=7.0))

        stats = review_service.get_album_stats(sample_album.id)
        assert stats.average_rating == 5.0
        # population std dev of [3.0, 7.0] = 2.0
        assert stats.rating_stddev == 2.0
        assert stats.review_count == 2
        assert stats.histogram[3].count == 1
        assert stats.histogram[7].count == 1

    def test_rating_ten_falls_in_last_bucket(self, review_service, sample_album, sample_user):
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=10.0))
        stats = review_service.get_album_stats(sample_album.id)
        assert stats.histogram[9].count == 1

    def test_rating_nine_falls_in_last_bucket(self, review_service, sample_album, sample_user):
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=9.0))
        stats = review_service.get_album_stats(sample_album.id)
        assert stats.histogram[9].count == 1

    def test_drafts_excluded_from_stats(self, review_service, sample_album, sample_user, user_factory):
        other = user_factory(email="other@test.com", username="other_reviewer")
        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=8.0))
        review_service.create_review(
            sample_album.id, other.id, ReviewCreate(rating=2.0, is_draft=True)
        )
        stats = review_service.get_album_stats(sample_album.id)
        assert stats.review_count == 1
        assert stats.average_rating == 8.0


@contextmanager
def _count_statements(db_session, match: str):
    """Count SQL statements containing ``match`` issued inside the block.

    These services used to fan a per-row query out across group members,
    nominators and co-reviewers, which is invisible in a correctness test and
    ruinous against a connection where every statement is a round trip. Pinning
    the statement count is the only thing that keeps the N+1 from quietly
    growing back.
    """
    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany):
        if match in statement:
            statements.append(statement)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", record)


class TestReviewQueryCounts:
    """Round-trip budgets for the paths that run on every review write."""

    def _member(self, db_session, group, user_factory, n: int):
        user = user_factory(email=f"m{n}@test.com", username=f"member_{n}")
        group.members.append(user)
        db_session.commit()
        return user

    def test_avg_refresh_does_not_scale_with_nominations(
        self, db_session, review_service, sample_group, sample_album, sample_user, user_factory
    ):
        """One SELECT against group_members no matter how many nominators there are.

        group_albums rows are keyed by (group, album, added_by), so a
        co-nominated album has several rows per group — and the membership
        lookup used to repeat verbatim for every one of them.
        """
        for n in range(4):
            member = self._member(db_session, sample_group, user_factory, n)
            db_session.add(
                GroupAlbum(
                    group_id=sample_group.id, album_id=sample_album.id, added_by=member.id
                )
            )
        db_session.add(
            GroupAlbum(
                group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id
            )
        )
        db_session.commit()

        with _count_statements(db_session, "group_members") as statements:
            review_service._refresh_group_album_avgs(sample_album.id)

        assert len(statements) == 1, statements

    def test_avg_refresh_is_flat_across_groups(
        self, db_session, review_service, sample_group_service, sample_album, sample_user
    ):
        """Nominating the same album in more groups must not add round trips."""
        from app.schemas.group import GroupCreate

        groups = [
            sample_group_service.create_group(GroupCreate(name=f"group_{n}"), sample_user)
            for n in range(3)
        ]
        for group in groups:
            db_session.add(
                GroupAlbum(group_id=group.id, album_id=sample_album.id, added_by=sample_user.id)
            )
        db_session.commit()

        with _count_statements(db_session, "group_members") as statements:
            review_service._refresh_group_album_avgs(sample_album.id)

        assert len(statements) == 1, statements

    def test_avg_refresh_still_scopes_to_each_group(
        self,
        db_session,
        review_service,
        sample_group,
        sample_group_service,
        sample_album,
        sample_user,
        user_factory,
    ):
        """Batching must not blur the per-group membership scope.

        Two groups nominate the same album and each has one member; each group
        album must cache only its own member's rating.
        """
        from app.schemas.group import GroupCreate

        outsider = user_factory(email="out@test.com", username="outsider_r")
        other_group = sample_group_service.create_group(GroupCreate(name="other group"), outsider)

        ga_mine = GroupAlbum(
            group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id
        )
        ga_other = GroupAlbum(
            group_id=other_group.id, album_id=sample_album.id, added_by=outsider.id
        )
        db_session.add_all([ga_mine, ga_other])
        db_session.commit()

        review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=4.0))
        review_service.create_review(sample_album.id, outsider.id, ReviewCreate(rating=10.0))

        db_session.refresh(ga_mine)
        db_session.refresh(ga_other)
        assert (ga_mine.avg_rating, ga_mine.review_count) == (4.0, 1)
        assert (ga_other.avg_rating, ga_other.review_count) == (10.0, 1)

    def test_co_reviewer_notification_is_one_insert(
        self, db_session, review_service, sample_group, sample_album, sample_user, user_factory
    ):
        """All co-reviewers in a group are notified with a single INSERT.

        ``NotificationService.create`` commits per call, so the old per-recipient
        loop cost roughly three round trips each.
        """
        members = [self._member(db_session, sample_group, user_factory, n) for n in range(5)]
        db_session.add(
            GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        )
        db_session.commit()

        for member in members:
            review_service.create_review(sample_album.id, member.id, ReviewCreate(rating=6.0))

        with _count_statements(db_session, "INSERT INTO notifications") as statements:
            review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=9.0))

        assert len(statements) == 1, statements
        # Every co-reviewer still got exactly one notification naming the reviewer.
        ns = NotificationService(db_session)
        for member in members:
            from_reviewer = [
                n for n in ns.get_unread(member) if sample_user.username in n.message
            ]
            assert len(from_reviewer) == 1, member.username

    def test_co_reviewer_lookup_does_not_scale_with_members(
        self, db_session, review_service, sample_group, sample_album, sample_user, user_factory
    ):
        """One membership SELECT for the whole fan-out, not one per group album row."""
        members = [self._member(db_session, sample_group, user_factory, n) for n in range(4)]
        for member in members:
            db_session.add(
                GroupAlbum(
                    group_id=sample_group.id, album_id=sample_album.id, added_by=member.id
                )
            )
        db_session.commit()
        for member in members:
            review_service.create_review(sample_album.id, member.id, ReviewCreate(rating=6.0))

        with _count_statements(db_session, "group_members") as statements:
            review_service._notify_co_reviewers(sample_album.id, members[0].id)

        assert len(statements) == 1, statements

    def test_album_stats_is_a_single_query(
        self, review_service, sample_album, sample_user, user_factory
    ):
        """The histogram and moments come from one pass over one result set."""
        for n in range(6):
            user = user_factory(email=f"s{n}@test.com", username=f"stats_{n}")
            review_service.create_review(sample_album.id, user.id, ReviewCreate(rating=float(n)))

        with _count_statements(review_service.db, "FROM reviews") as statements:
            review_service.get_album_stats(sample_album.id)

        assert len(statements) == 1, statements
