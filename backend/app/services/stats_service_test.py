from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from app.models import GroupAlbum, NominationGuess, Review
from fastapi import HTTPException, status
from sqlalchemy import event


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

        result = stats_service.get_album_guess_stats(
            sample_group.id, sample_group_album.id, other.id
        )

        assert result.group_album_id == sample_group_album.id
        assert result.nominator_user_id == sample_user.id
        assert result.total_guesses == 2
        assert result.correct_guesses == 1
        assert len(result.guesses) == 2
        assert result.revealed is True

    def test_album_guess_stats_not_found(self, stats_service, sample_group, sample_user):
        with pytest.raises(HTTPException) as exc_info:
            stats_service.get_album_guess_stats(sample_group.id, 99999, sample_user.id)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_no_guesses_returns_empty(
        self, stats_service, sample_group, sample_group_album, sample_user
    ):
        result = stats_service.get_album_guess_stats(
            sample_group.id, sample_group_album.id, sample_user.id
        )
        assert result.total_guesses == 0
        assert result.correct_guesses == 0
        assert result.guesses == []
        assert result.revealed is True

    def test_hidden_from_member_who_has_not_guessed(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)
        _mark_selected(db_session, sample_group_album)
        _add_guess(db_session, sample_group_album, other, sample_user)  # correct

        result = stats_service.get_album_guess_stats(
            sample_group.id, sample_group_album.id, third.id
        )

        assert result.revealed is False
        assert result.guesses == []
        assert result.total_guesses == 0
        assert result.correct_guesses == 0
        assert result.nominator_user_id is None
        assert result.nominator_username is None

    def test_revealed_once_viewer_has_guessed(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)
        _mark_selected(db_session, sample_group_album)
        _add_guess(db_session, sample_group_album, other, sample_user)  # correct
        _add_guess(db_session, sample_group_album, third, other)         # wrong

        result = stats_service.get_album_guess_stats(
            sample_group.id, sample_group_album.id, third.id
        )

        assert result.revealed is True
        assert len(result.guesses) == 2
        assert result.nominator_user_id == sample_user.id

    def test_revealed_to_nominator_without_guessing(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)
        _add_guess(db_session, sample_group_album, other, sample_user)

        # sample_user nominated the album, so cannot guess it — nothing to protect
        result = stats_service.get_album_guess_stats(
            sample_group.id, sample_group_album.id, sample_user.id
        )

        assert result.revealed is True
        assert len(result.guesses) == 1

    def test_chaos_guess_in_stats(
        self, stats_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)
        chaos_guess = NominationGuess(
            group_album_id=sample_group_album.id,
            guessing_user_id=other.id,
            guessed_user_id=None,
            correct=False,
        )
        db_session.add(chaos_guess)
        db_session.commit()

        result = stats_service.get_album_guess_stats(
            sample_group.id, sample_group_album.id, other.id
        )

        assert result.total_guesses == 1
        assert len(result.guesses) == 1
        g = result.guesses[0]
        assert g.is_chaos is True
        assert g.guessed_user_id is None
        assert g.guessed_username is None


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


@contextmanager
def _count_statements(db_session, match: str):
    """Count SQL statements containing ``match`` issued inside the block."""
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


class TestStatsQueryCounts:
    """Round-trip budgets for the guess breakdowns."""

    def test_album_guess_stats_does_not_scale_with_guesses(
        self,
        db_session,
        stats_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
    ):
        """Usernames are joined in, not walked off each guess.

        The breakdown needs two usernames per guess and the nominator's. Read
        through the relationships that is 2N+1 extra round trips, each one
        fetching a whole User row for one string.
        """
        _mark_selected(db_session, sample_group_album)
        guessers = []
        for n in range(6):
            guesser = user_factory(email=f"g{n}@test.com", username=f"guesser_{n}")
            sample_group_service.add_user(sample_group.id, guesser.id)
            _add_guess(db_session, sample_group_album, guesser, sample_user)
            guessers.append(guesser)

        with _count_statements(db_session, "FROM users") as statements:
            result = stats_service.get_album_guess_stats(
                sample_group.id, sample_group_album.id, sample_user.id
            )

        assert len(statements) <= 1, statements
        assert result.total_guesses == 6
        assert {g.guessing_username for g in result.guesses} == {
            f"guesser_{n}" for n in range(6)
        }
        assert all(g.guessed_username == sample_user.username for g in result.guesses)

    def test_user_guess_stats_counts_in_the_database(
        self,
        db_session,
        stats_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
    ):
        """The totals are aggregated in SQL rather than by hydrating every guess."""
        _mark_selected(db_session, sample_group_album)
        other = user_factory(email="counter@test.com", username="counter_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _add_guess(db_session, sample_group_album, other, sample_user)  # correct

        with _count_statements(db_session, "nomination_guesses") as statements:
            result = stats_service.get_user_guess_stats(other.id, sample_group.id)

        assert len(statements) == 1, statements
        assert "count" in statements[0].lower()
        assert (result.total_guesses, result.correct_guesses) == (1, 1)
        assert result.accuracy == 1.0
