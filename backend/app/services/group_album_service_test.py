from datetime import datetime, timezone

import pytest
from app.models import GroupAlbum
from app.schemas.group_album import NominationGuessCreate
from fastapi import HTTPException, status


def _mark_selected(db_session, group_album: GroupAlbum):
    """Set selected_date to simulate cron having selected this album."""
    group_album.selected_date = datetime.now(tz=timezone.utc)
    db_session.commit()
    db_session.refresh(group_album)


# ==================== DAILY SELECTION ====================


class TestSelectDailyAlbums:
    def test_select_one_album(
        self, group_album_service, sample_group, sample_group_album
    ):
        results = group_album_service.select_daily_albums(sample_group.id, n=1)

        assert len(results) == 1
        assert results[0].id == sample_group_album.id
        assert results[0].selected_date is not None

    def test_select_multiple_albums(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        from app.models import Album

        album2 = Album(spotify_album_id="spotify_2", title="Kid A", artist="Radiohead")
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)

        ga2 = GroupAlbum(
            group_id=sample_group.id, album_id=album2.id, added_by=sample_user.id
        )
        db_session.add(ga2)
        db_session.commit()

        results = group_album_service.select_daily_albums(sample_group.id, n=2)
        assert len(results) == 2
        assert all(ga.selected_date is not None for ga in results)

    def test_select_skips_already_selected(
        self, group_album_service, sample_group, sample_group_album, db_session
    ):
        _mark_selected(db_session, sample_group_album)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_daily_albums(sample_group.id, n=1)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_select_not_enough_available(
        self, group_album_service, sample_group, sample_group_album
    ):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_daily_albums(sample_group.id, n=5)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_select_empty_group_raises(self, group_album_service, sample_group):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_daily_albums(sample_group.id, n=1)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_multi_nomination_counts_as_one_album(
        self, group_album_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session
    ):
        """Two nominations for the same album should count as one selectable album."""
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        ga2 = GroupAlbum(
            group_id=sample_group.id,
            album_id=sample_group_album.album_id,
            added_by=other.id,
        )
        db_session.add(ga2)
        db_session.commit()

        results = group_album_service.select_daily_albums(sample_group.id, n=1)
        assert len(results) == 1

    def test_multi_nomination_all_marked_selected(
        self, group_album_service, sample_group, sample_group_album, sample_user,
        sample_group_service, user_factory, db_session
    ):
        """Selecting a multiply-nominated album marks ALL nominations as selected."""
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        ga2 = GroupAlbum(
            group_id=sample_group.id,
            album_id=sample_group_album.album_id,
            added_by=other.id,
        )
        db_session.add(ga2)
        db_session.commit()
        db_session.refresh(ga2)

        group_album_service.select_daily_albums(sample_group.id, n=1)

        db_session.refresh(sample_group_album)
        db_session.refresh(ga2)
        assert sample_group_album.selected_date is not None
        assert ga2.selected_date is not None


class TestTriggerDailySelection:
    def test_selects_when_none_today(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        results = group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert len(results) == 1
        assert results[0].selected_date is not None

    def test_idempotent_returns_existing(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        _mark_selected(db_session, sample_group_album)
        results = group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert len(results) == 1
        assert results[0].id == sample_group_album.id

    def test_non_member_forbidden(
        self, group_album_service, sample_group, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.trigger_daily_selection(sample_group.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_not_enough_albums_raises(
        self, group_album_service, sample_group, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_respects_daily_album_count(
        self, group_album_service, sample_group, sample_group_album, sample_user,
        db_session
    ):
        from app.models import Album, GroupSettings

        album2 = Album(spotify_album_id="spotify_2", title="Kid A", artist="Radiohead")
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)
        ga2 = GroupAlbum(group_id=sample_group.id, album_id=album2.id, added_by=sample_user.id)
        db_session.add(ga2)

        settings = db_session.query(GroupSettings).filter_by(group_id=sample_group.id).first()
        settings.daily_album_count = 2
        db_session.commit()

        results = group_album_service.trigger_daily_selection(sample_group.id, sample_user)
        assert len(results) == 2


class TestGetTodaysAlbums:
    def test_returns_todays_selections(
        self, group_album_service, sample_group, sample_group_album, sample_user, db_session
    ):
        _mark_selected(db_session, sample_group_album)
        results = group_album_service.get_todays_albums(sample_group.id, sample_user)
        assert len(results) == 1
        assert results[0].id == sample_group_album.id

    def test_excludes_unselected(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        results = group_album_service.get_todays_albums(sample_group.id, sample_user)
        assert results == []

    def test_non_member_forbidden(
        self, group_album_service, sample_group, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_todays_albums(sample_group.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== GUESSING ====================


class TestCheckGuess:
    def test_correct_guess(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)

        # other guesses sample_user (the actual nominator)
        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        assert result.correct is True
        assert sample_user.id in result.nominator_user_ids
        assert sample_user.username in result.nominator_usernames
        assert result.guess.guessing_user_id == other.id

    def test_incorrect_guess(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, third.id)
        _mark_selected(db_session, sample_group_album)

        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=third.id),  # wrong guess
        )

        assert result.correct is False
        assert sample_user.id in result.nominator_user_ids  # actual nominator revealed anyway

    def test_correct_guess_for_co_nominator(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        """Guessing any co-nominator of a multiply-nominated album should be correct."""
        other = user_factory(email="other@test.com", username="other_user")
        guesser = user_factory(email="guesser@test.com", username="guesser")
        sample_group_service.add_user(sample_group.id, other.id)
        sample_group_service.add_user(sample_group.id, guesser.id)

        # other also nominates the same album
        co_nomination = GroupAlbum(
            group_id=sample_group.id,
            album_id=sample_group_album.album_id,
            added_by=other.id,
        )
        db_session.add(co_nomination)
        db_session.commit()

        # Mark both as selected
        _mark_selected(db_session, sample_group_album)
        co_nomination.selected_date = sample_group_album.selected_date
        db_session.commit()

        # Guessing the co-nominator should be correct
        result = group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            guesser,
            NominationGuessCreate(guessed_user_id=other.id),
        )

        assert result.correct is True
        assert other.id in result.nominator_user_ids
        assert sample_user.id in result.nominator_user_ids

    def test_not_selected_raises(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                other,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_self_guess_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
    ):
        _mark_selected(db_session, sample_group_album)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                sample_user,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_duplicate_guess_conflict(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)

        group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                other,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_non_member_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        user_factory,
        db_session,
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        _mark_selected(db_session, sample_group_album)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.check_guess(
                sample_group.id,
                sample_group_album.id,
                outsider,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestGetMyGuess:
    def test_get_my_guess_success(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        _mark_selected(db_session, sample_group_album)
        group_album_service.check_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        result = group_album_service.get_my_guess(sample_group.id, sample_group_album.id, other)
        assert result.guess.guessing_user_id == other.id
        assert result.correct is True
        assert sample_user.id in result.nominator_user_ids
        assert sample_user.username in result.nominator_usernames

    def test_get_my_guess_not_found(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_my_guess(
                sample_group.id, sample_group_album.id, sample_user
            )
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_non_member_forbidden(
        self, group_album_service, sample_group, sample_group_album, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_my_guess(
                sample_group.id, sample_group_album.id, outsider
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
