"""Tests for PublicSpinService: the anonymous-visitor daily public draw."""

from datetime import timedelta

import pytest
from app.models import Album, GroupAlbum, PublicSpinDraw
from app.services.public_spin_service import PublicSpinService
from app.utils.time_helpers import DEFAULT_TZ, group_today
from fastapi import HTTPException, status


@pytest.fixture
def public_spin_service(db_session) -> PublicSpinService:
    return PublicSpinService(db_session)


@pytest.fixture
def nominate_albums(db_session, sample_user):
    """Factory: create N albums nominated to a group by sample_user."""

    def _nominate(group, n: int, *, prefix: str = "pubspin") -> list[GroupAlbum]:
        gas = []
        for i in range(n):
            album = Album(spotify_album_id=f"spotify_{prefix}_{i}", title=f"Album {prefix} {i}", artist="Artist")
            db_session.add(album)
            db_session.flush()
            ga = GroupAlbum(group_id=group.id, album_id=album.id, added_by=sample_user.id)
            db_session.add(ga)
            gas.append(ga)
        db_session.commit()
        for ga in gas:
            db_session.refresh(ga)
        return gas

    return _nominate


class TestPublicSpinDraw:
    def test_no_global_group_returns_503(self, public_spin_service):
        with pytest.raises(HTTPException) as exc_info:
            public_spin_service.get_or_create_todays_draw()
        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_creates_draw_from_global_pool(
        self, db_session, public_spin_service, global_group, sample_group, nominate_albums
    ):
        nominated = nominate_albums(sample_group, 3)

        result = public_spin_service.get_or_create_todays_draw()

        assert result.draw_date == group_today(DEFAULT_TZ)
        assert len(result.albums) == 3
        assert {a.album_id for a in result.albums} == {ga.album_id for ga in nominated}

    def test_caps_at_three_albums(
        self, db_session, public_spin_service, global_group, sample_group, nominate_albums
    ):
        nominate_albums(sample_group, 5)

        result = public_spin_service.get_or_create_todays_draw()

        assert len(result.albums) == 3

    def test_empty_pool_returns_empty_albums(self, public_spin_service, global_group):
        result = public_spin_service.get_or_create_todays_draw()
        assert result.albums == []

    def test_second_request_same_day_returns_cached_draw(
        self, db_session, public_spin_service, global_group, sample_group, nominate_albums
    ):
        nominate_albums(sample_group, 3)

        first = public_spin_service.get_or_create_todays_draw()
        second = public_spin_service.get_or_create_todays_draw()

        assert [a.album_id for a in first.albums] == [a.album_id for a in second.albums]
        assert db_session.query(PublicSpinDraw).count() == 1

    def test_drawn_albums_become_canonical_global_group_albums(
        self, db_session, public_spin_service, global_group, sample_group, nominate_albums
    ):
        nominated = nominate_albums(sample_group, 1)

        result = public_spin_service.get_or_create_todays_draw()

        canonical = (
            db_session.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == global_group.id,
                GroupAlbum.album_id == nominated[0].album_id,
            )
            .all()
        )
        assert len(canonical) == 1
        assert result.albums[0].album_id == nominated[0].album_id

    def test_reuses_existing_draw_row_for_the_day(
        self, db_session, public_spin_service, global_group, sample_group, nominate_albums
    ):
        nominated = nominate_albums(sample_group, 1)
        today = group_today(DEFAULT_TZ)
        db_session.add(PublicSpinDraw(draw_date=today, album_ids=[nominated[0].album_id]))
        db_session.commit()

        result = public_spin_service.get_or_create_todays_draw()

        assert db_session.query(PublicSpinDraw).count() == 1
        assert [a.album_id for a in result.albums] == [nominated[0].album_id]

    def test_ignores_draws_from_other_days(
        self, db_session, public_spin_service, global_group, sample_group, nominate_albums
    ):
        nominated = nominate_albums(sample_group, 1)
        yesterday = group_today(DEFAULT_TZ) - timedelta(days=1)
        db_session.add(PublicSpinDraw(draw_date=yesterday, album_ids=[999999]))
        db_session.commit()

        result = public_spin_service.get_or_create_todays_draw()

        assert db_session.query(PublicSpinDraw).count() == 2
        assert [a.album_id for a in result.albums] == [nominated[0].album_id]
