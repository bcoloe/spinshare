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
from app.schemas.group_album import CheckGuessResponse, NominationGuessResponse
from app.services.group_album_service import GroupAlbumService
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_mock_album(id=1):
    a = MagicMock()
    a.id = id
    a.spotify_album_id = "spotify_abc"
    a.title = "OK Computer"
    a.artist = "Radiohead"
    a.release_date = "1997-05"
    a.cover_url = None
    a.added_at = _NOW
    a.genres = []
    return a


def make_mock_group_album(id=1, group_id=1, album_id=1, added_by=1, selected_date=_NOW):
    ga = MagicMock()
    ga.id = id
    ga.group_id = group_id
    ga.album_id = album_id
    ga.added_by = added_by
    ga.status = "pending"
    ga.added_at = _NOW
    ga.selected_date = selected_date
    ga.albums = make_mock_album()
    return ga


def make_mock_guess_response(id=1, group_album_id=1, guessing_user_id=2, guessed_user_id=1, correct=True):
    return NominationGuessResponse(
        id=id,
        group_album_id=group_album_id,
        guessing_user_id=guessing_user_id,
        guessed_user_id=guessed_user_id,
        correct=correct,
        created_at=_NOW,
    )


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


# ==================== DAILY SELECTION ====================


class TestGetTodaysAlbums:
    def test_returns_list(self, client, mock_svc):
        mock_svc.get_todays_albums.return_value = [make_mock_group_album()]
        resp = client.get("/groups/1/albums/today")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 1

    def test_empty_list(self, client, mock_svc):
        mock_svc.get_todays_albums.return_value = []
        resp = client.get("/groups/1/albums/today")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

    def test_non_member_forbidden(self, client, mock_svc):
        mock_svc.get_todays_albums.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.get("/groups/1/albums/today")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/albums/today")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== TRIGGER DAILY SELECTION ====================


class TestTriggerDailySelection:
    def test_triggers_selection(self, client, mock_svc):
        mock_svc.trigger_daily_selection.return_value = [make_mock_group_album()]
        resp = client.post("/groups/1/albums/select-today")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 1
        mock_svc.trigger_daily_selection.assert_called_once()

    def test_returns_existing_when_already_selected(self, client, mock_svc):
        mock_svc.trigger_daily_selection.return_value = [make_mock_group_album(id=1), make_mock_group_album(id=2, album_id=2)]
        resp = client.post("/groups/1/albums/select-today")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 2

    def test_non_member_forbidden(self, client, mock_svc):
        mock_svc.trigger_daily_selection.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.post("/groups/1/albums/select-today")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_not_enough_albums_conflict(self, client, mock_svc):
        mock_svc.trigger_daily_selection.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Not enough unselected albums"
        )
        resp = client.post("/groups/1/albums/select-today")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/albums/select-today")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== GUESSING ====================


class TestCheckGuess:
    def test_correct_guess(self, client, mock_svc):
        mock_svc.check_guess.return_value = CheckGuessResponse(
            guess=make_mock_guess_response(),
            correct=True,
            nominator_user_ids=[1],
            nominator_usernames=["test_user"],
            is_chaos_selection=False,
        )
        resp = client.post("/groups/1/albums/1/check-guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["correct"] is True
        assert body["nominator_user_ids"] == [1]
        assert body["nominator_usernames"] == ["test_user"]
        mock_svc.check_guess.assert_called_once()

    def test_incorrect_guess(self, client, mock_svc):
        mock_svc.check_guess.return_value = CheckGuessResponse(
            guess=make_mock_guess_response(guessed_user_id=99),
            correct=False,
            nominator_user_ids=[1],
            nominator_usernames=["test_user"],
            is_chaos_selection=False,
        )
        resp = client.post("/groups/1/albums/1/check-guess", json={"guessed_user_id": 99})
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["correct"] is False

    def test_not_selected_conflict(self, client, mock_svc):
        mock_svc.check_guess.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Album not selected"
        )
        resp = client.post("/groups/1/albums/1/check-guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_self_guess_forbidden(self, client, mock_svc):
        mock_svc.check_guess.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot guess yourself"
        )
        resp = client.post("/groups/1/albums/1/check-guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_duplicate_guess_conflict(self, client, mock_svc):
        mock_svc.check_guess.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already guessed"
        )
        resp = client.post("/groups/1/albums/1/check-guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_non_member_forbidden(self, client, mock_svc):
        mock_svc.check_guess.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.post("/groups/1/albums/1/check-guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/albums/1/check-guess", json={"guessed_user_id": 1})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetMyGuess:
    def test_success(self, client, mock_svc):
        guess = MagicMock()
        guess.id = 1
        guess.group_album_id = 1
        guess.guessing_user_id = 1
        guess.guessed_user_id = 2
        guess.created_at = _NOW
        mock_svc.get_my_guess.return_value = guess
        resp = client.get("/groups/1/albums/1/guess/me")
        assert resp.status_code == status.HTTP_200_OK

    def test_not_found(self, client, mock_svc):
        mock_svc.get_my_guess.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No guess"
        )
        resp = client.get("/groups/1/albums/1/guess/me")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/albums/1/guess/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
