"""Tests for ArtistService.get_artist_overview."""

import pytest
from app.models import Album, GroupAlbum
from app.models.group import Group
from app.models.review import Review
from app.models.user import User
from fastapi import HTTPException, status

_DUMMY_HASH = "dummy_hash_for_testing"


def _user(db_session, username: str) -> User:
    user = User(email=f"{username}@test.com", username=username, password_hash=_DUMMY_HASH)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _group(db_session, name: str, owner: User) -> Group:
    group = Group(name=name, is_public=True, created_by=owner.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    return group


def _album(db_session, title: str, artist: str) -> Album:
    album = Album(title=title, artist=artist, spotify_album_id=f"sp_{title}")
    db_session.add(album)
    db_session.commit()
    db_session.refresh(album)
    return album


def _nominate(db_session, group: Group, album: Album, user: User) -> GroupAlbum:
    ga = GroupAlbum(group_id=group.id, album_id=album.id, added_by=user.id)
    db_session.add(ga)
    db_session.commit()
    return ga


def _review(db_session, album: Album, user: User, rating: float, is_draft: bool = False) -> Review:
    review = Review(album_id=album.id, user_id=user.id, rating=rating, is_draft=is_draft)
    db_session.add(review)
    db_session.commit()
    return review


class TestArtistOverview:
    def test_aggregates_nominated_albums(self, artist_service, db_session):
        alice = _user(db_session, "alice")
        bob = _user(db_session, "bob")
        g1 = _group(db_session, "G1", alice)
        g2 = _group(db_session, "G2", bob)

        a1 = _album(db_session, "Album One", "Muse")
        a2 = _album(db_session, "Album Two", "Muse")

        # a1 nominated by alice (in two groups) and bob → 2 distinct people
        _nominate(db_session, g1, a1, alice)
        _nominate(db_session, g2, a1, alice)
        _nominate(db_session, g1, a1, bob)
        # a2 nominated by bob only → 1 distinct person
        _nominate(db_session, g1, a2, bob)

        # a1: ratings 8 and 6 (avg 7.0); a2: rating 4 (avg 4.0)
        _review(db_session, a1, alice, 8)
        _review(db_session, a1, bob, 6)
        _review(db_session, a2, bob, 4)

        result = artist_service.get_artist_overview("Muse")

        assert result.artist == "Muse"
        assert result.album_count == 2
        # distinct-people nominations: a1=2, a2=1
        assert result.total_nominations == 3
        assert result.total_reviews == 3
        # mean of album averages: (7.0 + 4.0) / 2 = 5.5
        assert result.average_rating == 5.5
        # population std dev of album averages [7.0, 4.0] = 1.5
        assert result.rating_stddev == 1.5

        by_id = {item.album.id: item for item in result.albums}
        assert by_id[a1.id].nomination_count == 2
        assert by_id[a1.id].review_count == 2
        assert by_id[a1.id].average_rating == 7.0
        # population std dev of a1 ratings [8, 6] = 1.0
        assert by_id[a1.id].rating_stddev == 1.0
        assert by_id[a2.id].nomination_count == 1
        assert by_id[a2.id].average_rating == 4.0
        # single rating → std dev 0.0
        assert by_id[a2.id].rating_stddev == 0.0

        # Highest mean score is listed first (a1 avg 7.0 > a2 avg 4.0).
        assert result.albums[0].album.id == a1.id

    def test_albums_ordered_by_descending_mean_score(self, artist_service, db_session):
        alice = _user(db_session, "alice")
        g1 = _group(db_session, "G1", alice)
        low = _album(db_session, "Low", "Tool")
        high = _album(db_session, "High", "Tool")
        unrated = _album(db_session, "Unrated", "Tool")
        for album in (low, high, unrated):
            _nominate(db_session, g1, album, alice)
        _review(db_session, low, alice, 3)
        _review(db_session, high, alice, 9)
        # `unrated` has no published review

        result = artist_service.get_artist_overview("Tool")
        titles = [item.album.title for item in result.albums]
        assert titles == ["High", "Low", "Unrated"]

    def test_case_insensitive_match(self, artist_service, db_session):
        alice = _user(db_session, "alice")
        g1 = _group(db_session, "G1", alice)
        album = _album(db_session, "Album", "Radiohead")
        _nominate(db_session, g1, album, alice)

        result = artist_service.get_artist_overview("radiohead")
        assert result.artist == "Radiohead"
        assert result.album_count == 1

    def test_excludes_non_nominated_albums(self, artist_service, db_session):
        alice = _user(db_session, "alice")
        g1 = _group(db_session, "G1", alice)
        nominated = _album(db_session, "Nominated", "Beck")
        _album(db_session, "Orphan", "Beck")  # in DB but never nominated
        _nominate(db_session, g1, nominated, alice)

        result = artist_service.get_artist_overview("Beck")
        assert result.album_count == 1
        assert result.albums[0].album.title == "Nominated"

    def test_draft_reviews_ignored(self, artist_service, db_session):
        alice = _user(db_session, "alice")
        g1 = _group(db_session, "G1", alice)
        album = _album(db_session, "Album", "Bjork")
        _nominate(db_session, g1, album, alice)
        _review(db_session, album, alice, 9, is_draft=True)

        result = artist_service.get_artist_overview("Bjork")
        assert result.total_reviews == 0
        assert result.average_rating is None
        assert result.rating_stddev is None
        assert result.albums[0].average_rating is None
        assert result.albums[0].rating_stddev is None

    def test_unknown_artist_404(self, artist_service, db_session):
        with pytest.raises(HTTPException) as exc:
            artist_service.get_artist_overview("Nobody")
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    def test_blank_name_404(self, artist_service, db_session):
        with pytest.raises(HTTPException) as exc:
            artist_service.get_artist_overview("   ")
        assert exc.value.status_code == status.HTTP_404_NOT_FOUND
