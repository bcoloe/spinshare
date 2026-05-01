import pytest
from app.models import GroupAlbum
from app.models.notification import Notification
from app.schemas.album import ReviewCreate, ReviewUpdate
from app.schemas.notification import NotificationType
from app.services.notification_service import NotificationService
from fastapi import HTTPException, status


class TestReviewServiceCreate:
    def test_create_review_success(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=8.5, comment="Great album")
        review = review_service.create_review(sample_album.id, sample_user.id, data)

        assert review.id is not None
        assert review.album_id == sample_album.id
        assert review.user_id == sample_user.id
        assert review.rating == 8.5
        assert review.comment == "Great album"
        assert review.reviewed_at is not None

    def test_create_review_no_comment(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=7.0)
        review = review_service.create_review(sample_album.id, sample_user.id, data)
        assert review.comment is None

    def test_create_review_duplicate_conflict(self, review_service, sample_album, sample_user):
        data = ReviewCreate(rating=5.0)
        review_service.create_review(sample_album.id, sample_user.id, data)
        with pytest.raises(HTTPException) as exc_info:
            review_service.create_review(sample_album.id, sample_user.id, ReviewCreate(rating=6.0))
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT


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
        assert "other_reviewer" in unread[0].message

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
