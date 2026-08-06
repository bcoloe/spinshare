"""Tests for RecapService — weekly recap computation, persistence, and reads."""

from datetime import date, datetime, timezone

import pytest

from app.models import Album, GroupAlbum, GroupRecap, NominationGuess, RecapView, Review, User
from app.models.group import Group
from app.services.recap_service import RecapService
from app.utils.time_helpers import completed_week_bounds, week_start_for

# A fixed completed week: Mon 2026-07-27 → Mon 2026-08-03 (group tz defaults to ET).
WEEK_START = week_start_for(date(2026, 7, 27))
IN_WEEK = datetime(2026, 7, 29, 16, 0, tzinfo=timezone.utc)      # Wed noon ET
BEFORE_WEEK = datetime(2026, 7, 26, 16, 0, tzinfo=timezone.utc)  # Sun (prior week)
AFTER_WEEK = datetime(2026, 8, 4, 16, 0, tzinfo=timezone.utc)    # Tue (next week)


@pytest.fixture
def recap_service(db_session):
    return RecapService(db_session)


def _user(db, name) -> User:
    u = User(email=f"{name}@test.com", username=name, password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _album(db, title) -> Album:
    a = Album(spotify_album_id=f"sp_{title}", title=title, artist=f"{title} band", cover_url="http://c")
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _ga(db, group, album, added_by, added_at, selected_date=None) -> GroupAlbum:
    ga = GroupAlbum(
        group_id=group.id,
        album_id=album.id,
        added_by=added_by.id,
        added_at=added_at,
        selected_date=selected_date,
    )
    db.add(ga)
    db.commit()
    db.refresh(ga)
    return ga


def _review(db, user, album, rating, reviewed_at, is_draft=False) -> Review:
    r = Review(user_id=user.id, album_id=album.id, rating=rating, reviewed_at=reviewed_at, is_draft=is_draft)
    db.add(r)
    db.commit()
    return r


def _guess(db, ga, guesser, correct, created_at) -> NominationGuess:
    g = NominationGuess(
        group_album_id=ga.id,
        guessing_user_id=guesser.id,
        guessed_user_id=None,
        correct=correct,
        created_at=created_at,
    )
    db.add(g)
    db.commit()
    return g


@pytest.fixture
def scenario(db_session):
    """Seed one group with a fully-populated week of activity.

    Returns a dict of the key objects for assertions.
    """
    db = db_session
    alice, bob, carol = _user(db, "alice"), _user(db, "bob"), _user(db, "carol")
    group = Group(name="Recap Group", is_public=True, created_by=alice.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    group.members.extend([alice, bob, carol])
    db.commit()

    a1, a2, a3 = _album(db, "A1"), _album(db, "A2"), _album(db, "A3")

    # Nominations (albums added): alice x2, bob x1 in-week; carol's is out-of-week.
    ga1 = _ga(db, group, a1, alice, IN_WEEK, selected_date=IN_WEEK)   # drawn this week
    ga2 = _ga(db, group, a2, alice, IN_WEEK, selected_date=IN_WEEK)   # drawn this week
    _ga(db, group, a3, bob, IN_WEEK, selected_date=None)             # not drawn
    _ga(db, group, a3, carol, BEFORE_WEEK, selected_date=None)       # outside window

    # Reviews: alice reviews a1,a2 in-week; bob reviews a1 in-week; carol draft on a1;
    # alice reviews a3 before-week (excluded from leaderboard window).
    _review(db, alice, a1, 9, IN_WEEK)
    _review(db, bob, a1, 8, IN_WEEK)
    _review(db, alice, a2, 3, IN_WEEK)
    _review(db, carol, a1, 2, IN_WEEK, is_draft=True)   # draft → excluded
    _review(db, alice, a3, 7, BEFORE_WEEK)              # out of window → excluded

    # Guesses: 3 in-week (2 correct), 1 out-of-week.
    _guess(db, ga1, alice, True, IN_WEEK)
    _guess(db, ga1, bob, False, IN_WEEK)
    _guess(db, ga2, alice, True, IN_WEEK)
    _guess(db, ga2, bob, True, BEFORE_WEEK)             # out of window → excluded

    return {"group": group, "alice": alice, "bob": bob, "carol": carol, "a1": a1, "a2": a2}


class TestGenerate:
    def test_albums_added_leaderboard(self, recap_service, scenario):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        added = recap.data["albums_added"]
        assert {e["username"]: e["count"] for e in added} == {"alice": 2, "bob": 1}

    def test_albums_reviewed_leaderboard_excludes_drafts_and_out_of_window(self, recap_service, scenario):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        reviewed = {e["username"]: e["count"] for e in recap.data["albums_reviewed"]}
        assert reviewed == {"alice": 2, "bob": 1}  # carol's draft + alice's a3 excluded

    def test_favorite_and_least_favorite(self, recap_service, scenario):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        fav = recap.data["favorite_album"]
        least = recap.data["least_favorite_album"]
        assert fav["album_id"] == scenario["a1"].id
        assert fav["review_count"] == 2
        assert fav["avg_rating"] == 8.5
        assert least["album_id"] == scenario["a2"].id
        assert fav["weighted_score"] > least["weighted_score"]

    def test_least_favorite_none_with_single_reviewed_album(self, recap_service, scenario, db_session):
        # Remove a2's review so only a1 qualifies.
        db_session.query(Review).filter(Review.album_id == scenario["a2"].id).delete()
        db_session.commit()
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        assert recap.data["favorite_album"]["album_id"] == scenario["a1"].id
        assert recap.data["least_favorite_album"] is None

    def test_guess_accuracy(self, recap_service, scenario):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        acc = recap.data["guess_accuracy"]
        assert acc["total_guesses"] == 3
        assert acc["correct_guesses"] == 2
        assert acc["pct"] == 66.7
        per = {m["username"]: (m["total"], m["correct"], m["pct"]) for m in acc["per_member"]}
        assert per == {"alice": (2, 2, 100.0), "bob": (1, 0, 0.0)}

    def test_idempotent_returns_same_row(self, recap_service, scenario, db_session):
        first = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        second = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        assert first.id == second.id
        assert db_session.query(GroupRecap).filter(GroupRecap.group_id == scenario["group"].id).count() == 1

    def test_immutable_after_new_activity(self, recap_service, scenario, db_session):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        snapshot = dict(recap.data)
        # New review lands after generation — the frozen snapshot must not change.
        _review(db_session, scenario["bob"], scenario["a2"], 10, IN_WEEK)
        again = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        assert again.data == snapshot

    def test_force_regenerates(self, recap_service, scenario, db_session):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        _review(db_session, scenario["bob"], scenario["a2"], 10, IN_WEEK)
        regenerated = recap_service.generate_for_group(scenario["group"].id, WEEK_START, force=True)
        # a2 now has 2 reviews (bob 10 + alice 3) instead of 1.
        assert regenerated.data["least_favorite_album"]["review_count"] == 2
        assert db_session.query(GroupRecap).filter(GroupRecap.group_id == scenario["group"].id).count() == 1


class TestGenerateDue:
    def test_creates_recap_for_completed_week(self, recap_service, scenario):
        recap = recap_service.generate_due(scenario["group"].id)
        assert recap is not None
        expected_start, _ = completed_week_bounds("America/New_York")
        assert recap.week_start == expected_start

    def test_skips_global_group(self, recap_service, global_group):
        assert recap_service.generate_due(global_group.id) is None

    def test_skips_dealer_group(self, recap_service, scenario, db_session):
        from app.models import GroupSettings

        db_session.add(GroupSettings(group_id=scenario["group"].id, dealer_mode=True))
        db_session.commit()
        assert recap_service.generate_due(scenario["group"].id) is None

    def test_skips_bot_group(self, recap_service, scenario, db_session):
        from app.models.bot_source import BotSource

        db_session.add(
            BotSource(
                name="pitchfork-bot",
                bot_user_id=scenario["alice"].id,
                bot_group_id=scenario["group"].id,
            )
        )
        db_session.commit()
        assert recap_service.generate_due(scenario["group"].id) is None

    def test_generate_for_group_rejects_dealer(self, recap_service, scenario, db_session):
        from fastapi import HTTPException

        from app.models import GroupSettings

        db_session.add(GroupSettings(group_id=scenario["group"].id, dealer_mode=True))
        db_session.commit()
        with pytest.raises(HTTPException) as exc:
            recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        assert exc.value.status_code == 400

    def test_second_call_is_noop(self, recap_service, scenario, db_session):
        r1 = recap_service.generate_due(scenario["group"].id)
        r2 = recap_service.generate_due(scenario["group"].id)
        assert r1.id == r2.id
        assert db_session.query(GroupRecap).filter(GroupRecap.group_id == scenario["group"].id).count() == 1


class TestReads:
    def test_list_and_seen_flag(self, recap_service, scenario, db_session):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        alice = scenario["alice"]
        listed = recap_service.list_for_group(scenario["group"].id, alice)
        assert len(listed) == 1
        assert listed[0].seen is False

        recap_service.mark_seen(scenario["group"].id, recap.id, alice)
        assert recap_service.list_for_group(scenario["group"].id, alice)[0].seen is True

    def test_mark_seen_is_idempotent(self, recap_service, scenario, db_session):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        alice = scenario["alice"]
        recap_service.mark_seen(scenario["group"].id, recap.id, alice)
        recap_service.mark_seen(scenario["group"].id, recap.id, alice)
        assert db_session.query(RecapView).filter(RecapView.recap_id == recap.id).count() == 1

    def test_non_member_forbidden(self, recap_service, scenario, db_session):
        from fastapi import HTTPException

        recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        outsider = _user(db_session, "outsider")
        with pytest.raises(HTTPException) as exc:
            recap_service.list_for_group(scenario["group"].id, outsider)
        assert exc.value.status_code == 403

    def test_pending_for_user_reflects_views(self, recap_service, scenario):
        recap = recap_service.generate_for_group(scenario["group"].id, WEEK_START)
        alice = scenario["alice"]
        pending = recap_service.pending_for_user(alice)
        assert [p.id for p in pending] == [recap.id]
        assert pending[0].group_name == "Recap Group"

        recap_service.mark_seen(scenario["group"].id, recap.id, alice)
        assert recap_service.pending_for_user(alice) == []
