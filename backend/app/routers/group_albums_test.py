# backend/app/routers/group_albums_test.py
#
# Router tests for the GroupAlbum workflow endpoints. GroupAlbumService is
# fully mocked — business logic is tested in group_album_service_test.py.

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from app.dependencies import get_current_user, get_group_album_service
from app.main import app
from app.routers.conftest import make_mock_user
from app.services.group_album_service import GroupAlbumService
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_mock_album(id=1, spotify_album_id="spotify_abc", title="OK Computer", artist="Radiohead"):
    a = MagicMock()
    a.id = id
    a.spotify_album_id = spotify_album_id
    a.title = title
    a.artist = artist
    a.release_date = "1997-05"
    a.cover_url = None
    a.added_at = _NOW
    a.genres = []
    return a


def make_mock_group_album(
    id=1, group_id=1, album_id=1, added_by=1, status="pending"
) -> MagicMock:
    ga = MagicMock()
    ga.id = id
    ga.group_id = group_id
    ga.album_id = album_id
    ga.added_by = added_by
    ga.status = status
    ga.added_at = _NOW
    ga.selected_date = None
    ga.albums = make_mock_album()
    return ga


def make_mock_guess(id=1, group_album_id=1, guessing_user_id=2, guessed_user_id=1):
    g = MagicMock()
    g.id = id
    g.group_album_id = group_album_id
    g.guessing_user_id = guessing_user_id
    g.guessed_user_id = guessed_user_id
    g.created_at = _NOW
    return g


@pytest.fixture
def mock_svc():
    return MagicMock(spec=GroupAlbumService)


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def client(mock_user, mock_svc):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_group_album_service] = lambda: mock_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_svc):
    app.dependency_overrides[get_group_album_service] = lambda: mock_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==================== SELECTION ====================


class TestSelectAlbum:
    def test_select_random_success(self, client, mock_svc):
        mock_svc.select_album.return_value = make_mock_group_album(status="selected")
        resp = client.post("/groups/1/albums/select", json={})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "selected"
        mock_svc.select_album.assert_called_once()

    def test_select_specific_success(self, client, mock_svc):
        mock_svc.select_album.return_value = make_mock_group_album(id=3, status="selected")
        resp = client.post("/groups/1/albums/select", json={"group_album_id": 3})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == 3

    def test_select_no_pending_conflict(self, client, mock_svc):
        mock_svc.select_album.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No pending albums"
        )
        resp = client.post("/groups/1/albums/select", json={})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_select_non_admin_forbidden(self, client, mock_svc):
        mock_svc.select_album.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin"
        )
        resp = client.post("/groups/1/albums/select", json={})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_select_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/albums/select", json={})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetSelectedAlbum:
    def test_get_selected_success(self, client, mock_svc):
        mock_svc.get_selected_album.return_value = make_mock_group_album(status="selected")
        resp = client.get("/groups/1/albums/selected")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "selected"

    def test_get_selected_none(self, client, mock_svc):
        mock_svc.get_selected_album.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No album selected"
        )
        resp = client.get("/groups/1/albums/selected")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_get_selected_non_member(self, client, mock_svc):
        mock_svc.get_selected_album.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.get("/groups/1/albums/selected")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_get_selected_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/albums/selected")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== GUESSING ====================


class TestSubmitGuess:
    def test_submit_guess_success(self, client, mock_svc):
        mock_svc.submit_guess.return_value = make_mock_guess()
        resp = client.post("/groups/1/albums/1/guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["guessing_user_id"] == 2
        assert body["guessed_user_id"] == 1
        mock_svc.submit_guess.assert_called_once()

    def test_submit_guess_not_selected(self, client, mock_svc):
        mock_svc.submit_guess.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not selected"
        )
        resp = client.post("/groups/1/albums/1/guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_submit_guess_self_forbidden(self, client, mock_svc):
        mock_svc.submit_guess.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot guess yourself"
        )
        resp = client.post("/groups/1/albums/1/guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_submit_guess_duplicate(self, client, mock_svc):
        mock_svc.submit_guess.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already guessed"
        )
        resp = client.post("/groups/1/albums/1/guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_submit_guess_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/albums/1/guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestUpdateGuess:
    def test_update_guess_success(self, client, mock_svc):
        mock_svc.update_guess.return_value = make_mock_guess(guessed_user_id=3)
        resp = client.put("/groups/1/albums/1/guess", json={"guessed_user_id": 3})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["guessed_user_id"] == 3

    def test_update_guess_not_selected(self, client, mock_svc):
        mock_svc.update_guess.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not selected"
        )
        resp = client.put("/groups/1/albums/1/guess", json={"guessed_user_id": 3})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_update_guess_not_found(self, client, mock_svc):
        mock_svc.update_guess.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No prior guess"
        )
        resp = client.put("/groups/1/albums/1/guess", json={"guessed_user_id": 3})
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestGetMyGuess:
    def test_get_my_guess_success(self, client, mock_svc):
        mock_svc.get_my_guess.return_value = make_mock_guess()
        resp = client.get("/groups/1/albums/1/guess/me")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["guessing_user_id"] == 2

    def test_get_my_guess_not_found(self, client, mock_svc):
        mock_svc.get_my_guess.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No guess"
        )
        resp = client.get("/groups/1/albums/1/guess/me")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_get_my_guess_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/albums/1/guess/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== REVIEW PHASE ====================


class TestCompleteReviewPhase:
    def test_complete_review_phase_success(self, client, mock_svc):
        mock_svc.complete_review_phase.return_value = make_mock_group_album(status="reviewed")
        resp = client.post("/groups/1/albums/1/complete")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "reviewed"
        mock_svc.complete_review_phase.assert_called_once()

    def test_complete_review_phase_not_selected(self, client, mock_svc):
        mock_svc.complete_review_phase.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not selected"
        )
        resp = client.post("/groups/1/albums/1/complete")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_complete_review_phase_forbidden(self, client, mock_svc):
        mock_svc.complete_review_phase.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin"
        )
        resp = client.post("/groups/1/albums/1/complete")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_complete_review_phase_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/albums/1/complete")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== REVEAL ====================


class TestRevealNominator:
    def test_reveal_success(self, client, mock_svc):
        from app.schemas.group_album import GuessResultResponse, NominationRevealResponse

        mock_svc.reveal_nominator.return_value = NominationRevealResponse(
            group_album_id=1,
            nominator_user_id=1,
            nominator_username="test_user",
            guesses=[
                GuessResultResponse(
                    guessing_user_id=2,
                    guessing_username="other_user",
                    guessed_user_id=1,
                    guessed_username="test_user",
                    correct=True,
                )
            ],
        )
        resp = client.get("/groups/1/albums/1/reveal")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["nominator_user_id"] == 1
        assert body["nominator_username"] == "test_user"
        assert len(body["guesses"]) == 1
        assert body["guesses"][0]["correct"] is True

    def test_reveal_not_reviewed(self, client, mock_svc):
        mock_svc.reveal_nominator.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not yet reviewed"
        )
        resp = client.get("/groups/1/albums/1/reveal")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_reveal_non_member_forbidden(self, client, mock_svc):
        mock_svc.reveal_nominator.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.get("/groups/1/albums/1/reveal")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_reveal_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/albums/1/reveal")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
