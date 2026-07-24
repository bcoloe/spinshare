# backend/app/routers/group_albums_test.py
#
# Router tests for the GroupAlbum workflow endpoints. GroupAlbumService is
# fully mocked — business logic is tested in group_album_service_test.py.

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from app.dependencies import get_current_user, get_dealer_service, get_group_album_service
from app.main import app
from app.routers.conftest import make_mock_user
from app.schemas.album import AlbumResponse, GroupAlbumResponse
from app.schemas.group_album import (
    CheckGuessResponse,
    DealRollResponse,
    DealsTodayResponse,
    NominationGuessResponse,
)
from app.services.dealer_service import DealerService
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
    a.youtube_music_id = None
    a.apple_music_album_id = None
    a.artist_url = None
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


def make_deal_response(album_id=1, group_album_id=1):
    return GroupAlbumResponse(
        id=group_album_id,
        group_id=1,
        album_id=album_id,
        added_by=1,
        status="pending",
        added_at=_NOW,
        selected_date=None,
        dealt_at=_NOW,
        album=AlbumResponse(
            id=album_id,
            title="OK Computer",
            artist="Radiohead",
            added_at=_NOW,
        ),
    )


@pytest.fixture
def mock_svc():
    return MagicMock(spec=GroupAlbumService)


@pytest.fixture
def mock_dealer_svc():
    return MagicMock(spec=DealerService)


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def client(mock_user, mock_svc, mock_dealer_svc):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_group_album_service] = lambda: mock_svc
    app.dependency_overrides[get_dealer_service] = lambda: mock_dealer_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_svc, mock_dealer_svc):
    app.dependency_overrides[get_group_album_service] = lambda: mock_svc
    app.dependency_overrides[get_dealer_service] = lambda: mock_dealer_svc
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


# ==================== DEALER MODE ====================


class TestRollDeal:
    def test_roll_returns_deal(self, client, mock_dealer_svc):
        mock_dealer_svc.roll.return_value = DealRollResponse(
            deal=make_deal_response(),
            rolls_used_today=1,
            rolls_per_day=2,
            pool_remaining=4,
        )
        resp = client.post("/groups/1/deals/roll")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["deal"]["dealt_at"] is not None
        assert body["rolls_used_today"] == 1
        assert body["rolls_per_day"] == 2
        assert body["pool_remaining"] == 4
        mock_dealer_svc.roll.assert_called_once()

    @pytest.mark.parametrize(
        "detail", ["dealer_mode_disabled", "no_rolls_remaining", "dealer_pool_empty"]
    )
    def test_roll_conflicts(self, client, mock_dealer_svc, detail):
        mock_dealer_svc.roll.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=detail
        )
        resp = client.post("/groups/1/deals/roll")
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert resp.json()["detail"] == detail

    def test_non_member_forbidden(self, client, mock_dealer_svc):
        mock_dealer_svc.roll.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.post("/groups/1/deals/roll")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/deals/roll")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetTodaysDeals:
    def test_returns_deals(self, client, mock_dealer_svc):
        mock_dealer_svc.get_todays_deals.return_value = DealsTodayResponse(
            deals=[make_deal_response()],
            rolls_used_today=1,
            rolls_per_day=1,
            pool_remaining=0,
        )
        resp = client.get("/groups/1/deals/today")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["deals"]) == 1

    def test_empty_when_dealer_off(self, client, mock_dealer_svc):
        mock_dealer_svc.get_todays_deals.return_value = DealsTodayResponse(
            deals=[], rolls_used_today=0, rolls_per_day=0, pool_remaining=0
        )
        resp = client.get("/groups/1/deals/today")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["deals"] == []

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/deals/today")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetMemberHistory:
    def test_returns_history(self, client, mock_dealer_svc):
        mock_dealer_svc.get_member_history.return_value = [make_deal_response()]
        resp = client.get("/groups/1/albums/history")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 1

    def test_non_member_forbidden(self, client, mock_dealer_svc):
        mock_dealer_svc.get_member_history.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.get("/groups/1/albums/history")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/albums/history")
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


class TestGetMyGroupGuesses:
    def test_success(self, client, mock_svc):
        mock_svc.get_my_guesses_for_group.return_value = [
            CheckGuessResponse(
                guess=make_mock_guess_response(id=1, group_album_id=1),
                correct=True,
                nominator_user_ids=[1],
                nominator_usernames=["test_user"],
                is_chaos_selection=False,
            ),
            CheckGuessResponse(
                guess=make_mock_guess_response(id=2, group_album_id=2),
                correct=False,
                nominator_user_ids=[2],
                nominator_usernames=["other_user"],
                is_chaos_selection=False,
            ),
        ]
        resp = client.get("/groups/1/guesses/me")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert len(body) == 2
        mock_svc.get_my_guesses_for_group.assert_called_once()

    def test_empty(self, client, mock_svc):
        mock_svc.get_my_guesses_for_group.return_value = []
        resp = client.get("/groups/1/guesses/me")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/guesses/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetMyGuess:
    def test_success(self, client, mock_svc):
        mock_svc.get_my_guess.return_value = CheckGuessResponse(
            guess=make_mock_guess_response(guessing_user_id=1, guessed_user_id=2),
            correct=False,
            nominator_user_ids=[3],
            nominator_usernames=["other_user"],
            is_chaos_selection=False,
            guessed_username="guessed_user",
        )
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
