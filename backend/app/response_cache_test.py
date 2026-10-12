"""Tests for the in-process response cache.

The unit tests pin the pieces: how SQL is classified, how versions move with
commits, when entries expire. The integration tests drive real endpoints against
the test database and check the properties the cache must never break: a hit
costs no query, one viewer never receives another's response, and a committed
write is visible on the very next read.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app import response_cache
from app.database import get_db
from app.main import app
from app.models import Album, Group, GroupAlbum, GroupInvitation, User, group_members
from app.response_cache import ResponseCache, classify, next_day_boundary, versions
from app.routers.conftest import _auth_headers_for

NY = ZoneInfo("America/New_York")


# ==================== UNIT ====================


class TestClassify:
    def test_reads_every_table_named(self):
        named, written = classify(
            "SELECT reviews.id FROM reviews JOIN group_albums ON group_albums.album_id = reviews.album_id"
        )
        assert named == {"reviews", "group_albums"}
        assert written == set()

    @pytest.mark.parametrize("sql, target", [
        ("INSERT INTO reviews (album_id) VALUES (1)", "reviews"),
        ('UPDATE "groups" SET name=%(name)s WHERE "groups".id = 1', "groups"),
        ("DELETE FROM notifications WHERE notifications.id = 3", "notifications"),
        ("INSERT INTO reviews (id) VALUES (1) ON CONFLICT (id) DO UPDATE SET rating = 2", "reviews"),
    ])
    def test_writes_name_their_target(self, sql, target):
        assert classify(sql)[1] == {target}

    def test_locking_select_is_not_a_write(self):
        assert classify("SELECT * FROM group_albums WHERE id = 1 FOR UPDATE OF group_albums")[1] == set()

    def test_unknown_tables_are_ignored(self):
        assert classify("UPDATE alembic_version SET version_num='x'") == (frozenset(), frozenset())


class TestVersionsFollowRootTransactions:
    """What production does: a real COMMIT or ROLLBACK, not a test savepoint.

    The statements match no rows, so nothing is left behind in the test database.
    """

    def test_root_commit_bumps(self, engine):
        before = versions.snapshot().get("notifications", 0)
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM notifications WHERE id = -1"))
            conn.commit()
        assert versions.snapshot().get("notifications", 0) == before + 1

    def test_root_rollback_discards(self, engine):
        before = versions.snapshot().get("notifications", 0)
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM notifications WHERE id = -1"))
            conn.rollback()
            conn.execute(text("SELECT 1"))
            conn.commit()  # a later, read-only commit must not publish the discarded write
        assert versions.snapshot().get("notifications", 0) == before


class TestVersionsFollowCommits:
    def test_committed_write_bumps_its_table(self, db_session):
        before = versions.snapshot().get("notifications", 0)
        db_session.execute(text("DELETE FROM notifications WHERE id = -1"))
        db_session.commit()
        assert versions.snapshot().get("notifications", 0) > before

    def test_rolled_back_write_does_not(self, db_session):
        before = versions.snapshot().get("notifications", 0)
        db_session.execute(text("DELETE FROM notifications WHERE id = -1"))
        db_session.rollback()
        assert versions.snapshot().get("notifications", 0) == before

    def test_reads_do_not(self, db_session):
        before = versions.snapshot()
        db_session.execute(text("SELECT count(*) FROM notifications")).scalar()
        db_session.commit()
        assert versions.snapshot() == before


class TestDayBoundary:
    def test_earliest_local_midnight_wins(self):
        now = datetime(2026, 10, 12, 12, tzinfo=UTC)  # 08:00 NY, 21:00 Tokyo
        boundary = next_day_boundary(now, ["America/New_York", "Asia/Tokyo"])
        assert boundary == datetime(2026, 10, 13, tzinfo=ZoneInfo("Asia/Tokyo"))

    def test_no_zones_falls_back_to_the_default(self):
        now = datetime(2026, 10, 12, 12, tzinfo=UTC)
        assert next_day_boundary(now, []) == datetime(2026, 10, 13, tzinfo=NY)


class TestStore:
    @pytest.fixture
    def store(self):
        now = datetime(2026, 10, 12, 12, tzinfo=NY)
        return ResponseCache(max_bytes=1000, clock=lambda: now)

    def test_entry_expires_at_valid_until(self, store):
        store.store("k", "v", {}, size=10, valid_until=store.clock() + timedelta(hours=1))
        assert store.lookup("k").value == "v"
        store.clock = lambda: datetime(2026, 10, 12, 13, 1, tzinfo=NY)
        assert store.lookup("k") is None

    def test_entry_expires_at_local_midnight(self, store):
        store.store("k", "v", {}, size=10)
        store.clock = lambda: datetime(2026, 10, 13, 0, 0, tzinfo=NY)
        assert store.lookup("k") is None

    def test_already_expired_answer_is_not_stored(self, store):
        store.store("k", "v", {}, size=10, valid_until=store.clock() - timedelta(seconds=1))
        assert store.lookup("k") is None

    def test_entry_dies_when_a_table_it_read_changes(self, store):
        store.store("k", "v", {"reviews": versions.snapshot().get("reviews", 0)}, size=10)
        versions.bump(["reviews"])
        assert store.lookup("k") is None

    def test_bounded_by_bytes_least_recent_first(self, store):
        store.store("a", 1, {}, size=400)
        store.store("b", 2, {}, size=400)
        store.lookup("a")  # touch a, so b is least recent
        store.store("c", 3, {}, size=400)
        assert store.lookup("a") is not None
        assert store.lookup("b") is None

    def test_oversized_entry_is_skipped(self, store):
        store.store("big", 1, {}, size=5000)
        assert store.lookup("big") is None


class TestValidUntil:
    def test_noop_outside_a_cached_computation(self):
        response_cache.valid_until(datetime.now(UTC))  # must not raise

    def test_earliest_declaration_wins(self):
        with response_cache._observe() as observed:
            response_cache.valid_until(datetime(2026, 1, 2, tzinfo=UTC))
            response_cache.valid_until(datetime(2026, 1, 1, tzinfo=UTC))
            response_cache.valid_until(datetime(2026, 1, 3, tzinfo=UTC))
        assert observed.valid_until == datetime(2026, 1, 1, tzinfo=UTC)


# ==================== INTEGRATION ====================


@pytest.fixture
def cache_on():
    """Run with the shared cache enabled and empty; restore its state afterwards."""
    cache = response_cache.cache
    enabled, clock = cache.enabled, cache.clock
    cache.enabled = True
    cache.clear()
    yield cache
    cache.clear()
    cache.enabled, cache.clock = enabled, clock


@pytest.fixture
def api(db_session, cache_on):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def statements(db_session):
    """Count SQL statements issued on the test connection."""
    count = {"n": 0}
    conn = db_session.connection()

    def bump(*_):
        count["n"] += 1

    event.listen(conn, "before_cursor_execute", bump)
    yield count
    event.remove(conn, "before_cursor_execute", bump)


@pytest.fixture
def world(db_session):
    """alice and bob share a group with one drawn album; carol is an outsider."""
    alice, bob, carol = (User(email=f"{n}@test.com", username=n, password_hash="x") for n in ("alice", "bob", "carol"))
    group = Group(name="Cached", is_public=False, creator=alice)
    album = Album(spotify_album_id="cache_1", title="Spiderland", artist="Slint")
    db_session.add_all([alice, bob, carol, group, album])
    db_session.flush()
    db_session.execute(group_members.insert(), [
        {"group_id": group.id, "user_id": alice.id, "role": "owner"},
        {"group_id": group.id, "user_id": bob.id, "role": "member"},
    ])
    db_session.add(GroupAlbum(group_id=group.id, album_id=album.id, added_by=alice.id,
                              selected_date=datetime.now(UTC)))
    db_session.commit()
    return {"alice": alice, "bob": bob, "carol": carol, "group": group, "album": album}


class TestServing:
    def test_repeat_load_is_answered_without_a_query(self, api, world, statements):
        url, headers = f"/groups/{world['group'].id}/members", _auth_headers_for(world["alice"])

        first = api.get(url, headers=headers)
        statements["n"] = 0
        second = api.get(url, headers=headers)

        assert first.headers["x-cache"] == "MISS" and second.headers["x-cache"] == "HIT"
        assert second.status_code == 200 and second.content == first.content
        assert second.headers["content-type"] == first.headers["content-type"]
        assert statements["n"] == 0

    def test_one_viewer_never_receives_anothers_response(self, api, world):
        url = f"/groups/{world['group'].id}/members"
        assert api.get(url, headers=_auth_headers_for(world["alice"])).status_code == 200

        outsider = api.get(url, headers=_auth_headers_for(world["carol"]))

        assert outsider.status_code == 403
        assert outsider.headers.get("x-cache") != "HIT"

    def test_refusals_are_not_cached(self, api, world, cache_on):
        url, headers = f"/groups/{world['group'].id}/members", _auth_headers_for(world["carol"])
        api.get(url, headers=headers)
        stored = cache_on.stats.stored
        assert api.get(url, headers=headers).status_code == 403
        assert cache_on.stats.stored == stored

    def test_bad_token_bypasses_the_cache_and_is_still_refused(self, api, world, cache_on):
        url = f"/groups/{world['group'].id}/members"
        api.get(url, headers=_auth_headers_for(world["alice"]))

        resp = api.get(url, headers={"Authorization": "Bearer not-a-token"})

        assert resp.status_code == 401
        assert cache_on.stats.bypassed == 1

    def test_uncached_route_is_left_alone(self, api, world):
        resp = api.get("/users/me", headers=_auth_headers_for(world["alice"]))
        assert resp.status_code == 200 and "x-cache" not in resp.headers

    def test_disabled_cache_passes_through(self, api, world, cache_on):
        cache_on.enabled = False
        resp = api.get(f"/groups/{world['group'].id}/members", headers=_auth_headers_for(world["alice"]))
        assert resp.status_code == 200 and "x-cache" not in resp.headers


class TestCoherence:
    def test_a_committed_write_is_seen_on_the_next_read(self, api, world):
        album, group = world["album"], world["group"]
        url = f"/albums/{album.id}/reviews?group_id={group.id}"
        alice, bob = _auth_headers_for(world["alice"]), _auth_headers_for(world["bob"])
        # alice posts first so she may see others' reviews (#175).
        assert api.post(f"/albums/{album.id}/reviews?group_id={group.id}", headers=alice,
                        json={"rating": 8, "comment": "mine"}).status_code in (200, 201)
        before = api.get(url, headers=alice)
        assert api.get(url, headers=alice).headers["x-cache"] == "HIT"

        assert api.post(f"/albums/{album.id}/reviews?group_id={group.id}", headers=bob,
                        json={"rating": 3, "comment": "bob's take"}).status_code in (200, 201)
        after = api.get(url, headers=alice)

        assert after.headers["x-cache"] == "MISS"
        assert "bob's take" in after.text and "bob's take" not in before.text

    def test_membership_change_reaches_the_member_list(self, api, world, db_session):
        url, headers = f"/groups/{world['group'].id}/members", _auth_headers_for(world["alice"])
        assert "carol" not in api.get(url, headers=headers).text

        db_session.execute(group_members.insert().values(group_id=world["group"].id, user_id=world["carol"].id))
        db_session.commit()

        assert "carol" in api.get(url, headers=headers).text

    def test_expiring_invitation_bounds_its_entry(self, api, world, db_session, cache_on):
        expires = datetime.now(UTC) + timedelta(hours=1)
        db_session.add(GroupInvitation(group_id=world["group"].id, invited_email="carol@test.com",
                                       invited_by=world["alice"].id, token="t-cache", expires_at=expires))
        db_session.commit()
        headers = _auth_headers_for(world["carol"])
        assert len(api.get("/invitations/pending", headers=headers).json()) == 1

        cache_on.clock = lambda: expires + timedelta(seconds=1)

        assert api.get("/invitations/pending", headers=headers).headers["x-cache"] == "MISS"

    def test_entries_do_not_outlive_the_local_day(self, api, world, cache_on):
        url, headers = f"/groups/{world['group'].id}/members", _auth_headers_for(world["alice"])
        api.get(url, headers=headers)

        tomorrow = datetime.now(NY).date() + timedelta(days=1)
        cache_on.clock = lambda: datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=NY)

        assert api.get(url, headers=headers).headers["x-cache"] == "MISS"


class TestRefresh:
    """A session's first call — the token refresh — must not wake the database twice."""

    @staticmethod
    def _refresh(api, user):
        from app.utils.security import create_refresh_token

        token = create_refresh_token({"sub": str(user.id), "email": user.email})
        return api.post(f"/users/refresh?refresh_token={token}")

    def test_repeat_refresh_needs_no_query(self, api, world, statements):
        assert self._refresh(api, world["alice"]).status_code == 200
        statements["n"] = 0
        assert self._refresh(api, world["alice"]).status_code == 200
        assert statements["n"] == 0

    def test_new_membership_reaches_the_next_token(self, api, world, db_session):
        from app.utils.security import decode_access_token

        self._refresh(api, world["carol"])
        db_session.execute(group_members.insert().values(group_id=world["group"].id, user_id=world["carol"].id))
        db_session.commit()

        token = self._refresh(api, world["carol"]).json()["access_token"]

        assert decode_access_token(token)["groups"] == [world["group"].id]

    def test_deleted_user_cannot_refresh(self, api, world, db_session):
        carol = world["carol"]
        self._refresh(api, carol)
        db_session.delete(carol)
        db_session.commit()
        assert self._refresh(api, carol).status_code == 401
