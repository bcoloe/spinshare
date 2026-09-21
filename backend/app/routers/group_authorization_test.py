# backend/app/routers/group_authorization_test.py
#
# Regression tests for the group authorization gates in app/dependencies.py.
#
# Unlike the other router test modules, these wire the *real* GroupService to the
# test database: the whole point is that the gate consults real membership. The
# services behind each endpoint are still mocked, so a 200 here means "the gate
# let the request through", not "the query worked".
#
# Before these gates existed, every endpoint below injected current_user purely to
# force a login and then read the group without ever checking membership — any
# authenticated user could page through a private group by guessing its id.

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from app.database import get_db
from app.dependencies import (
    get_album_service,
    get_group_album_service,
    get_group_service,
    get_participation_service,
    get_review_service,
    get_stats_service,
)
from app.main import app
from app.models import Group, GroupAlbum, User
from app.models.group import GroupRole, group_members
from app.routers.conftest import _auth_headers_for
from app.schemas.participation import ParticipationResponse
from app.schemas.stats import AlbumGuessStatsResponse, UserGuessStatsResponse
from app.services.group_service import GroupService
from fastapi import status
from fastapi.testclient import TestClient

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_DUMMY_HASH = "dummy_hash_for_testing"


# ==================== DB FIXTURES ====================


def _make_user(db_session, username: str) -> User:
    user = User(email=f"{username}@test.com", username=username, password_hash=_DUMMY_HASH)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_group(db_session, name: str, owner: User | None, *, is_public: bool) -> Group:
    group = Group(
        name=name,
        is_public=is_public,
        is_global=False,
        created_by=owner.id if owner else None,
    )
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    if owner is not None:
        db_session.execute(
            group_members.insert().values(
                group_id=group.id, user_id=owner.id, role=GroupRole.Owner.value
            )
        )
        db_session.commit()
    return group


@pytest.fixture
def member(db_session) -> User:
    return _make_user(db_session, "gate_member")


@pytest.fixture
def outsider(db_session) -> User:
    return _make_user(db_session, "gate_outsider")


@pytest.fixture
def private_group(db_session, member) -> Group:
    return _make_group(db_session, "Gate Private", member, is_public=False)


@pytest.fixture
def public_group(db_session, member) -> Group:
    return _make_group(db_session, "Gate Public", member, is_public=True)


@pytest.fixture
def private_group_album(db_session, private_group, member) -> GroupAlbum:
    from app.models import Album

    album = Album(spotify_album_id="spotify_gate_1", title="Kid A", artist="Radiohead")
    db_session.add(album)
    db_session.flush()
    ga = GroupAlbum(group_id=private_group.id, album_id=album.id, added_by=member.id)
    db_session.add(ga)
    db_session.commit()
    db_session.refresh(ga)
    return ga


# ==================== APP WIRING ====================


def _make_mock_group_album(id=1, group_id=1):
    album = MagicMock()
    album.id = 1
    album.spotify_album_id = "spotify_gate_1"
    album.title = "Kid A"
    album.artist = "Radiohead"
    album.release_date = None
    album.cover_url = None
    album.youtube_music_id = None
    album.apple_music_album_id = None
    album.artist_url = None
    album.wikipedia_url = None
    album.wikipedia_checked_at = None
    album.added_at = _NOW
    album.genres = []

    ga = MagicMock()
    ga.id = id
    ga.group_id = group_id
    ga.album_id = 1
    ga.added_by = 1
    ga.status = "pending"
    ga.added_at = _NOW
    ga.selected_date = None
    ga.albums = album
    return ga


@pytest.fixture
def client(db_session):
    """TestClient with a real GroupService (so the gates see real membership).

    Every service the gated endpoints delegate to is mocked, so any non-403 here
    is the gate's verdict rather than the endpoint's business logic.
    """
    album_svc = MagicMock()
    album_svc.get_group_albums.return_value = []
    album_svc.get_group_album.return_value = _make_mock_group_album()

    review_svc = MagicMock()
    review_svc.get_all_reviews_for_group.return_value = []
    review_svc.get_my_reviews_for_group.return_value = []

    stats_svc = MagicMock()
    stats_svc.get_user_guess_stats.return_value = UserGuessStatsResponse(
        user_id=1, group_id=1, total_guesses=0, correct_guesses=0, accuracy=0.0
    )
    stats_svc.get_album_guess_stats.return_value = AlbumGuessStatsResponse(
        group_album_id=1,
        nominator_user_id=None,
        nominator_username=None,
        total_guesses=0,
        correct_guesses=0,
        guesses=[],
        revealed=False,
    )

    group_album_svc = MagicMock()
    group_album_svc.get_my_guesses_for_group.return_value = []

    participation_svc = MagicMock()
    participation_svc.get_progress.return_value = ParticipationResponse(
        threshold=3, credits=0, can_pick=False
    )

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_group_service] = lambda: GroupService(db_session)
    app.dependency_overrides[get_album_service] = lambda: album_svc
    app.dependency_overrides[get_review_service] = lambda: review_svc
    app.dependency_overrides[get_stats_service] = lambda: stats_svc
    app.dependency_overrides[get_group_album_service] = lambda: group_album_svc
    app.dependency_overrides[get_participation_service] = lambda: participation_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _paths(group: Group, group_album_id: int, user: User) -> dict[str, str]:
    """Every endpoint the membership gates cover, keyed by a readable id."""
    return {
        "group_albums": f"/groups/{group.id}/albums",
        "group_album": f"/groups/{group.id}/albums/{group_album_id}",
        "group_reviews": f"/groups/{group.id}/reviews",
        "member_guess_stats": f"/stats/groups/{group.id}/members/{user.id}/guesses",
        "album_guess_stats": f"/stats/groups/{group.id}/albums/{group_album_id}/guesses",
        "my_guesses": f"/groups/{group.id}/guesses/me",
        "my_participation": f"/groups/{group.id}/participation/me",
        "my_reviews": f"/groups/{group.id}/reviews/me",
    }


_ALL_ENDPOINTS = [
    "group_albums",
    "group_album",
    "group_reviews",
    "member_guess_stats",
    "album_guess_stats",
    "my_guesses",
    "my_participation",
    "my_reviews",
]

# Endpoints a public group deliberately exposes to any logged-in caller — the
# group opted in to being public, and these carry no per-member secrets.
_PUBLIC_READABLE = ["group_albums", "group_album", "group_reviews"]


# ==================== PRIVATE GROUP ====================


class TestPrivateGroupRejectsNonMembers:
    @pytest.mark.parametrize("endpoint", _ALL_ENDPOINTS)
    def test_non_member_is_forbidden(
        self, client, private_group, private_group_album, member, outsider, endpoint
    ):
        path = _paths(private_group, private_group_album.id, member)[endpoint]
        resp = client.get(path, headers=_auth_headers_for(outsider))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("endpoint", _ALL_ENDPOINTS)
    def test_member_still_allowed(
        self, client, private_group, private_group_album, member, endpoint
    ):
        path = _paths(private_group, private_group_album.id, member)[endpoint]
        resp = client.get(path, headers=_auth_headers_for(member))
        assert resp.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize("endpoint", _ALL_ENDPOINTS)
    def test_anonymous_is_unauthorized(
        self, client, private_group, private_group_album, member, endpoint
    ):
        path = _paths(private_group, private_group_album.id, member)[endpoint]
        assert client.get(path).status_code == status.HTTP_401_UNAUTHORIZED


class TestSiteAdminExemption:
    def test_admin_may_read_a_private_group(
        self, client, db_session, private_group, private_group_album, member, outsider
    ):
        outsider.is_admin = True
        db_session.commit()
        path = _paths(private_group, private_group_album.id, member)["group_albums"]
        resp = client.get(path, headers=_auth_headers_for(outsider))
        assert resp.status_code == status.HTTP_200_OK


# ==================== PUBLIC GROUP ====================


class TestPublicGroupStaysReadable:
    """A public group's content must not be locked away by the new gates."""

    @pytest.mark.parametrize("endpoint", _PUBLIC_READABLE)
    def test_non_member_may_read_public_group_content(
        self, client, public_group, private_group_album, member, outsider, endpoint
    ):
        path = _paths(public_group, private_group_album.id, member)[endpoint]
        resp = client.get(path, headers=_auth_headers_for(outsider))
        assert resp.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize(
        "endpoint", [e for e in _ALL_ENDPOINTS if e not in _PUBLIC_READABLE]
    )
    def test_member_only_endpoints_stay_closed_on_a_public_group(
        self, client, public_group, private_group_album, member, outsider, endpoint
    ):
        # Being public makes a group's catalogue readable; it does not make a
        # stranger a participant in its guessing game or priority-pick ledger.
        path = _paths(public_group, private_group_album.id, member)[endpoint]
        resp = client.get(path, headers=_auth_headers_for(outsider))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestGlobalGroupStaysReadable:
    def test_non_member_may_read_the_global_group_catalogue(
        self, client, db_session, private_group_album, member, outsider
    ):
        group = Group(name="Gate Global", is_public=True, is_global=True, created_by=None)
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)

        resp = client.get(f"/groups/{group.id}/albums", headers=_auth_headers_for(outsider))
        assert resp.status_code == status.HTTP_200_OK

    def test_non_member_may_read_a_public_bot_group_catalogue(
        self, client, db_session, member, outsider
    ):
        from app.models import BotSource

        group = _make_group(db_session, "Gate Bot", member, is_public=True)
        bot_user = _make_user(db_session, "gate_bot_user")
        db_session.add(
            BotSource(name="gate-bot", bot_user_id=bot_user.id, bot_group_id=group.id)
        )
        db_session.commit()

        resp = client.get(f"/groups/{group.id}/albums", headers=_auth_headers_for(outsider))
        assert resp.status_code == status.HTTP_200_OK


class TestAnonymousTolerantGate:
    """``require_group_read_access(allow_anonymous=True)`` on a throwaway route.

    No shipped route opts in yet — the gated endpoints all kept their existing
    "must be logged in" floor — but the variant exists for the landing-page reads,
    so pin the semantics it inherits from ``require_public_or_member``.
    """

    @pytest.fixture
    def anon_client(self, db_session):
        from app.dependencies import require_group_read_access
        from fastapi import Depends, FastAPI

        probe = FastAPI()

        @probe.get("/probe/{group_id}", dependencies=[Depends(require_group_read_access(allow_anonymous=True))])
        def _probe(group_id: int):
            return {"ok": True}

        probe.dependency_overrides[get_db] = lambda: db_session
        probe.dependency_overrides[get_group_service] = lambda: GroupService(db_session)
        with TestClient(probe) as c:
            yield c

    def test_anonymous_may_read_the_global_group(self, anon_client, db_session):
        group = Group(name="Gate Global Anon", is_public=True, is_global=True, created_by=None)
        db_session.add(group)
        db_session.commit()
        db_session.refresh(group)

        assert anon_client.get(f"/probe/{group.id}").status_code == status.HTTP_200_OK

    def test_anonymous_is_rejected_on_an_ordinary_group(
        self, anon_client, db_session, member
    ):
        group = _make_group(db_session, "Gate Anon Public", member, is_public=True)

        # Public is about logged-in strangers, not the open internet.
        assert anon_client.get(f"/probe/{group.id}").status_code == status.HTTP_401_UNAUTHORIZED


# ==================== DEAD ROUTE REMOVAL ====================


class TestTodaysAlbumsRouteIsNotDuplicated:
    def test_only_one_handler_is_registered(self):
        """The shadowed, ungated copy in albums.py is gone.

        Two routes shared this path; only the first-registered one (the workflow
        router's, which honours the group timezone and checks membership) could
        ever run, so the second was unreachable and weaker.
        """
        matches = [
            r
            for r in app.routes
            if getattr(r, "path", None) == "/groups/{group_id}/albums/today"
        ]
        assert len(matches) == 1
