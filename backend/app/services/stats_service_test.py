from datetime import datetime, timezone

import pytest
from app.models import GroupAlbum, NominationGuess, Review
from fastapi import HTTPException, status


def _mark_selected(db_session, group_album: GroupAlbum):
    group_album.selected_date = datetime.now(tz=timezone.utc)
    db_session.commit()
    db_session.refresh(group_album)


def _add_guess(db_session, group_album, guessing_user, guessed_user):
    correct = guessed_user.id == group_album.added_by
    guess = NominationGuess(
        group_album_id=group_album.id,
        guessing_user_id=guessing_user.id,
        guessed_user_id=guessed_user.id,
        correct=correct,
    )
    db_session.add(guess)
    db_session.commit()
    db_session.refresh(guess)
    return guess


def _add_review(db_session, album, user, rating, comment=None):
    review = Review(album_id=album.id, user_id=user.id, rating=rating, comment=comment)
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)
    return review


# ==================== GUESS ACCURACY ====================


class TestUserGuessStats:
    def test_correct_guess_accuracy(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)
        _add_guess(db_session, sample_group_album, other, sample_user)  # correct

        result = stats_service.get_user_guess_stats(other.id, sample_group.id)

        assert result.total_guesses == 1
        assert result.correct_guesses == 1
        assert result.accuracy == 1.0

    def test_incorrect_guess_accuracy(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)
        _mark_selected(db_session, sample_group_album)
        _add_guess(db_session, sample_group_album, other, third)  # wrong

        result = stats_service.get_user_guess_stats(other.id, sample_group.id)

        assert result.total_guesses == 1
        assert result.correct_guesses == 0
        assert result.accuracy == 0.0

    def test_mixed_accuracy(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session, sample_album,
    ):
        from app.models import Album

        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)

        # First album: other guesses correctly (nominator = sample_user)
        _mark_selected(db_session, sample_group_album)
        _add_guess(db_session, sample_group_album, other, sample_user)

        # Second album nominated by other, other guesses wrong
        album2 = Album(spotify_album_id="spotify_b2", title="Kid A", artist="Radiohead")
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)

        ga2 = GroupAlbum(group_id=sample_group.id, album_id=album2.id, added_by=other.id,
                         selected_date=datetime.now(tz=timezone.utc))
        db_session.add(ga2)
        db_session.commit()
        db_session.refresh(ga2)
        _add_guess(db_session, ga2, other, third)  # wrong (nominator was other)

        result = stats_service.get_user_guess_stats(other.id, sample_group.id)

        assert result.total_guesses == 2
        assert result.correct_guesses == 1
        assert result.accuracy == 0.5

    def test_no_guesses_returns_zero(
        self, stats_service, sample_group, sample_user
    ):
        result = stats_service.get_user_guess_stats(sample_user.id, sample_group.id)
        assert result.total_guesses == 0
        assert result.correct_guesses == 0
        assert result.accuracy == 0.0


class TestAlbumGuessStats:
    def test_album_guess_stats(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)
        _mark_selected(db_session, sample_group_album)
        _add_guess(db_session, sample_group_album, other, sample_user)   # correct
        _add_guess(db_session, sample_group_album, third, other)          # wrong

        result = stats_service.get_album_guess_stats(sample_group.id, sample_group_album.id)

        assert result.group_album_id == sample_group_album.id
        assert result.nominator_user_id == sample_user.id
        assert result.total_guesses == 2
        assert result.correct_guesses == 1
        assert len(result.guesses) == 2

    def test_album_guess_stats_not_found(self, stats_service, sample_group):
        with pytest.raises(HTTPException) as exc_info:
            stats_service.get_album_guess_stats(sample_group.id, 99999)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_no_guesses_returns_empty(
        self, stats_service, sample_group, sample_group_album
    ):
        result = stats_service.get_album_guess_stats(sample_group.id, sample_group_album.id)
        assert result.total_guesses == 0
        assert result.correct_guesses == 0
        assert result.guesses == []


# ==================== REVIEW STATS ====================


class TestAlbumReviewStats:
    def test_avg_rating(
        self, stats_service, sample_album, sample_user, user_factory, db_session
    ):
        other = user_factory(email="other@test.com", username="other_user")
        _add_review(db_session, sample_album, sample_user, 8.0)
        _add_review(db_session, sample_album, other, 6.0)

        result = stats_service.get_album_review_stats(sample_album.id)

        assert result.album_id == sample_album.id
        assert result.review_count == 2
        assert result.avg_rating == 7.0
        assert result.min_rating == 6.0
        assert result.max_rating == 8.0

    def test_single_review(
        self, stats_service, sample_album, sample_user, db_session
    ):
        _add_review(db_session, sample_album, sample_user, 9.5)

        result = stats_service.get_album_review_stats(sample_album.id)

        assert result.review_count == 1
        assert result.avg_rating == 9.5
        assert result.min_rating == 9.5
        assert result.max_rating == 9.5

    def test_no_reviews_raises(self, stats_service, sample_album):
        with pytest.raises(HTTPException) as exc_info:
            stats_service.get_album_review_stats(sample_album.id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
