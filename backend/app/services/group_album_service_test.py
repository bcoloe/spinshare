import pytest
from app.models import GroupAlbum, NominationGuess
from app.models.group import GroupRole
from app.schemas.group_album import NominationGuessCreate, SelectAlbumRequest
from fastapi import HTTPException, status


# ==================== HELPERS ====================


def _set_status(db_session, group_album: GroupAlbum, new_status: str):
    group_album.status = new_status
    db_session.commit()
    db_session.refresh(group_album)


# ==================== SELECTION ====================


class TestSelectAlbum:
    def test_select_random_pending(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        request = SelectAlbumRequest()
        result = group_album_service.select_album(sample_group.id, sample_user, request)

        assert result.status == "selected"
        assert result.id == sample_group_album.id

    def test_select_specific_album(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        request = SelectAlbumRequest(group_album_id=sample_group_album.id)
        result = group_album_service.select_album(sample_group.id, sample_user, request)

        assert result.status == "selected"
        assert result.id == sample_group_album.id

    def test_select_demotes_previous_selected(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
        sample_album,
    ):
        from app.models import Album

        album2 = Album(
            spotify_album_id="spotify_second",
            title="Kid A",
            artist="Radiohead",
        )
        db_session.add(album2)
        db_session.commit()
        db_session.refresh(album2)

        ga2 = GroupAlbum(
            group_id=sample_group.id,
            album_id=album2.id,
            added_by=sample_user.id,
            status="pending",
        )
        db_session.add(ga2)
        db_session.commit()
        db_session.refresh(ga2)

        # Select first album
        group_album_service.select_album(
            sample_group.id, sample_user, SelectAlbumRequest(group_album_id=sample_group_album.id)
        )

        # Select second album — first should be returned to pending
        group_album_service.select_album(
            sample_group.id, sample_user, SelectAlbumRequest(group_album_id=ga2.id)
        )

        db_session.refresh(sample_group_album)
        assert sample_group_album.status == "pending"

    def test_select_no_pending_raises(self, group_album_service, sample_group, sample_user):
        request = SelectAlbumRequest()
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_album(sample_group.id, sample_user, request)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_select_non_pending_specific_raises(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
    ):
        _set_status(db_session, sample_group_album, "reviewed")
        request = SelectAlbumRequest(group_album_id=sample_group_album.id)
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_album(sample_group.id, sample_user, request)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_select_non_admin_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_group_service,
        user_factory,
    ):
        member = user_factory(email="member@test.com", username="member_user")
        sample_group_service.add_user(sample_group.id, member.id)
        request = SelectAlbumRequest()
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.select_album(sample_group.id, member, request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestGetSelectedAlbum:
    def test_get_selected_success(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
    ):
        _set_status(db_session, sample_group_album, "selected")
        result = group_album_service.get_selected_album(sample_group.id, sample_user)
        assert result.id == sample_group_album.id
        assert result.status == "selected"

    def test_get_selected_none_raises(
        self, group_album_service, sample_group, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_selected_album(sample_group.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_selected_non_member_forbidden(
        self, group_album_service, sample_group, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_selected_album(sample_group.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== GUESSING ====================


class TestSubmitGuess:
    def test_submit_guess_success(
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
        _set_status(db_session, sample_group_album, "selected")

        guess = group_album_service.submit_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        assert guess.id is not None
        assert guess.guessing_user_id == other.id
        assert guess.guessed_user_id == sample_user.id

    def test_submit_guess_self_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
    ):
        _set_status(db_session, sample_group_album, "selected")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.submit_guess(
                sample_group.id,
                sample_group_album.id,
                sample_user,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_submit_guess_not_selected_raises(
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
        # album is still pending
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.submit_guess(
                sample_group.id,
                sample_group_album.id,
                other,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_submit_guess_duplicate_conflict(
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
        _set_status(db_session, sample_group_album, "selected")

        group_album_service.submit_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.submit_guess(
                sample_group.id,
                sample_group_album.id,
                other,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_submit_guess_non_member_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        user_factory,
        db_session,
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        _set_status(db_session, sample_group_album, "selected")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.submit_guess(
                sample_group.id,
                sample_group_album.id,
                outsider,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestUpdateGuess:
    def _setup_guess(
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
        _set_status(db_session, sample_group_album, "selected")
        group_album_service.submit_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )
        return other

    def test_update_guess_success(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = self._setup_guess(
            group_album_service,
            sample_group,
            sample_group_album,
            sample_user,
            sample_group_service,
            user_factory,
            db_session,
        )
        third = user_factory(email="third@test.com", username="third_user")
        sample_group_service.add_user(sample_group.id, third.id)

        updated = group_album_service.update_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=third.id),
        )
        assert updated.guessed_user_id == third.id

    def test_update_guess_not_selected_raises(
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
        _set_status(db_session, sample_group_album, "reviewed")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.update_guess(
                sample_group.id,
                sample_group_album.id,
                other,
                NominationGuessCreate(guessed_user_id=sample_user.id),
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT


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
        _set_status(db_session, sample_group_album, "selected")
        group_album_service.submit_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )

        result = group_album_service.get_my_guess(sample_group.id, sample_group_album.id, other)
        assert result.guessing_user_id == other.id

    def test_get_my_guess_not_found(
        self, group_album_service, sample_group, sample_group_album, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.get_my_guess(
                sample_group.id, sample_group_album.id, sample_user
            )
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ==================== REVIEW PHASE ====================


class TestCompleteReviewPhase:
    def test_complete_review_phase_success(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
    ):
        _set_status(db_session, sample_group_album, "selected")
        result = group_album_service.complete_review_phase(
            sample_group.id, sample_group_album.id, sample_user
        )
        assert result.status == "reviewed"

    def test_complete_review_phase_not_selected_raises(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
    ):
        # album is still pending
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.complete_review_phase(
                sample_group.id, sample_group_album.id, sample_user
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_complete_review_phase_non_admin_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_group_service,
        user_factory,
        db_session,
    ):
        member = user_factory(email="member@test.com", username="member_user")
        sample_group_service.add_user(sample_group.id, member.id)
        _set_status(db_session, sample_group_album, "selected")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.complete_review_phase(
                sample_group.id, sample_group_album.id, member
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== REVEAL ====================


class TestRevealNominator:
    def _setup_reviewed_album_with_guess(
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
        _set_status(db_session, sample_group_album, "selected")
        group_album_service.submit_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=sample_user.id),
        )
        _set_status(db_session, sample_group_album, "reviewed")
        return other

    def test_reveal_nominator_success(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        sample_group_service,
        user_factory,
        db_session,
    ):
        other = self._setup_reviewed_album_with_guess(
            group_album_service,
            sample_group,
            sample_group_album,
            sample_user,
            sample_group_service,
            user_factory,
            db_session,
        )

        result = group_album_service.reveal_nominator(
            sample_group.id, sample_group_album.id, sample_user
        )

        assert result.nominator_user_id == sample_user.id
        assert result.nominator_username == sample_user.username
        assert len(result.guesses) == 1
        assert result.guesses[0].guessing_user_id == other.id
        assert result.guesses[0].correct is True

    def test_reveal_guess_incorrect(
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
        _set_status(db_session, sample_group_album, "selected")
        # other guesses third, but actual nominator is sample_user
        group_album_service.submit_guess(
            sample_group.id,
            sample_group_album.id,
            other,
            NominationGuessCreate(guessed_user_id=third.id),
        )
        _set_status(db_session, sample_group_album, "reviewed")

        result = group_album_service.reveal_nominator(
            sample_group.id, sample_group_album.id, sample_user
        )
        assert result.guesses[0].correct is False

    def test_reveal_not_reviewed_raises(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        sample_user,
        db_session,
    ):
        _set_status(db_session, sample_group_album, "selected")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.reveal_nominator(
                sample_group.id, sample_group_album.id, sample_user
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_reveal_non_member_forbidden(
        self,
        group_album_service,
        sample_group,
        sample_group_album,
        user_factory,
        db_session,
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        _set_status(db_session, sample_group_album, "reviewed")
        with pytest.raises(HTTPException) as exc_info:
            group_album_service.reveal_nominator(
                sample_group.id, sample_group_album.id, outsider
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
