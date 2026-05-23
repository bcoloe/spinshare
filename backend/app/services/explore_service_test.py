"""Tests for ExploreService."""

import pytest

from app.models.album import Album
from app.models.group import Group
from app.models.group_album import GroupAlbum
from app.models.group_settings import GroupSettings
from app.models.review import Review
from app.services.explore_service import ExploreService


# ==================== FIXTURES ====================


@pytest.fixture
def explore_service(db_session) -> ExploreService:
    return ExploreService(db_session)


def _make_album(db, *, title: str, artist: str, artist_url: str | None = None) -> Album:
    album = Album(title=title, artist=artist, artist_url=artist_url, cover_url=None)
    db.add(album)
    db.commit()
    db.refresh(album)
    return album


def _make_group(db, *, name: str, is_public: bool = True, is_global: bool = False) -> Group:
    group = Group(name=name, is_public=is_public, is_global=is_global, created_by=None)
    db.add(group)
    db.commit()
    db.refresh(group)
    settings = GroupSettings(group_id=group.id)
    db.add(settings)
    db.commit()
    return group


def _nominate(db, *, group: Group, album: Album, user_id: int | None = None) -> GroupAlbum:
    ga = GroupAlbum(group_id=group.id, album_id=album.id, added_by=user_id)
    db.add(ga)
    db.commit()
    db.refresh(ga)
    return ga


def _review(db, *, album: Album, user_id: int, rating: float, is_draft: bool = False) -> Review:
    rv = Review(album_id=album.id, user_id=user_id, rating=rating, is_draft=is_draft)
    db.add(rv)
    db.commit()
    db.refresh(rv)
    return rv


# ==================== get_explore_albums ====================


class TestGetExploreAlbums:
    def test_returns_only_nominated_albums(self, explore_service, db_session):
        """Albums with no GroupAlbum rows are excluded."""
        group = _make_group(db_session, name="G1")
        nominated = _make_album(db_session, title="Nominated", artist="A")
        _make_album(db_session, title="Orphan", artist="B")
        _nominate(db_session, group=group, album=nominated)

        page = explore_service.get_explore_albums()
        ids = [a.id for a in page.items]
        assert nominated.id in ids
        # orphan album should not appear
        assert all(i != nominated.id + 1 or i in ids for i in ids)  # only nominated in list
        assert len(page.items) == 1

    def test_pagination_next_offset(self, explore_service, db_session):
        """next_offset is set when more results exist."""
        group = _make_group(db_session, name="G1")
        albums = [_make_album(db_session, title=f"Album {i}", artist="X") for i in range(5)]
        for a in albums:
            _nominate(db_session, group=group, album=a)

        page = explore_service.get_explore_albums(offset=0, limit=3)
        assert len(page.items) == 3
        assert page.next_offset == 3

    def test_pagination_last_page_no_next_offset(self, explore_service, db_session):
        group = _make_group(db_session, name="G1")
        for i in range(3):
            a = _make_album(db_session, title=f"A{i}", artist="X")
            _nominate(db_session, group=group, album=a)

        page = explore_service.get_explore_albums(offset=0, limit=10)
        assert page.next_offset is None

    def test_min_reviews_filter(self, explore_service, db_session, sample_user):
        group = _make_group(db_session, name="G1")
        album_with_reviews = _make_album(db_session, title="Reviewed", artist="X")
        album_no_reviews = _make_album(db_session, title="Bare", artist="Y")
        _nominate(db_session, group=group, album=album_with_reviews)
        _nominate(db_session, group=group, album=album_no_reviews)
        _review(db_session, album=album_with_reviews, user_id=sample_user.id, rating=8.0)

        page = explore_service.get_explore_albums(min_reviews=1)
        ids = [a.id for a in page.items]
        assert album_with_reviews.id in ids
        assert album_no_reviews.id not in ids

    def test_sort_by_most_nominated(self, explore_service, db_session):
        group1 = _make_group(db_session, name="G1")
        group2 = _make_group(db_session, name="G2")
        popular = _make_album(db_session, title="Popular", artist="X")
        niche = _make_album(db_session, title="Niche", artist="Y")
        # popular nominated in 2 groups, niche in 1
        _nominate(db_session, group=group1, album=popular)
        _nominate(db_session, group=group2, album=popular)
        _nominate(db_session, group=group1, album=niche)

        page = explore_service.get_explore_albums(sort_by="most_nominated")
        assert page.items[0].id == popular.id
        assert page.items[0].nomination_count == 2

    def test_review_count_and_avg_rating_populated(self, explore_service, db_session, sample_user):
        group = _make_group(db_session, name="G1")
        album = _make_album(db_session, title="Rated", artist="X")
        _nominate(db_session, group=group, album=album)
        _review(db_session, album=album, user_id=sample_user.id, rating=7.0)

        page = explore_service.get_explore_albums()
        item = next(a for a in page.items if a.id == album.id)
        assert item.review_count == 1
        assert item.avg_rating == 7.0

    def test_q_filters_by_title(self, explore_service, db_session):
        group = _make_group(db_session, name="G1")
        match = _make_album(db_session, title="OK Computer", artist="Radiohead")
        no_match = _make_album(db_session, title="Kind of Blue", artist="Miles Davis")
        _nominate(db_session, group=group, album=match)
        _nominate(db_session, group=group, album=no_match)

        page = explore_service.get_explore_albums(q="ok computer")
        ids = [a.id for a in page.items]
        assert match.id in ids
        assert no_match.id not in ids

    def test_q_filters_by_artist(self, explore_service, db_session):
        group = _make_group(db_session, name="G1")
        match = _make_album(db_session, title="Pablo Honey", artist="Radiohead")
        no_match = _make_album(db_session, title="Nevermind", artist="Nirvana")
        _nominate(db_session, group=group, album=match)
        _nominate(db_session, group=group, album=no_match)

        page = explore_service.get_explore_albums(q="radiohead")
        ids = [a.id for a in page.items]
        assert match.id in ids
        assert no_match.id not in ids

    def test_q_is_case_insensitive(self, explore_service, db_session):
        group = _make_group(db_session, name="G1")
        album = _make_album(db_session, title="Abbey Road", artist="The Beatles")
        _nominate(db_session, group=group, album=album)

        page = explore_service.get_explore_albums(q="ABBEY")
        assert any(a.id == album.id for a in page.items)

    def test_draft_reviews_excluded(self, explore_service, db_session, sample_user):
        group = _make_group(db_session, name="G1")
        album = _make_album(db_session, title="Draft", artist="X")
        _nominate(db_session, group=group, album=album)
        _review(db_session, album=album, user_id=sample_user.id, rating=9.0, is_draft=True)

        page = explore_service.get_explore_albums()
        item = next(a for a in page.items if a.id == album.id)
        assert item.review_count == 0
        assert item.avg_rating is None


# ==================== get_explore_groups ====================


class TestGetExploreGroups:
    def test_returns_public_groups(self, explore_service, db_session):
        pub = _make_group(db_session, name="Public Group")
        _make_group(db_session, name="Private Group", is_public=False)

        page = explore_service.get_explore_groups()
        ids = [g.id for g in page.items]
        assert pub.id in ids
        assert all(g.is_public for g in page.items)

    def test_includes_global_bot_groups(self, explore_service, db_session):
        bot = _make_group(db_session, name="Bot Group", is_public=True, is_global=True)

        page = explore_service.get_explore_groups()
        ids = [g.id for g in page.items]
        assert bot.id in ids
        item = next(g for g in page.items if g.id == bot.id)
        assert item.is_global is True

    def test_alphabetical_order(self, explore_service, db_session):
        _make_group(db_session, name="Zappa Fan Club")
        _make_group(db_session, name="Acid Jazz Society")
        _make_group(db_session, name="Metal Heads")

        page = explore_service.get_explore_groups()
        names = [g.name for g in page.items]
        assert names == sorted(names, key=str.lower)

    def test_pagination(self, explore_service, db_session):
        # Count any groups already present (CI seeds a global spinshare group via migration)
        baseline = len(explore_service.get_explore_groups(limit=100).items)

        for i in range(5):
            _make_group(db_session, name=f"Group {i:02d}")

        total = baseline + 5

        page = explore_service.get_explore_groups(offset=0, limit=3)
        assert len(page.items) == 3
        assert page.next_offset == 3

        page2 = explore_service.get_explore_groups(offset=3, limit=3)
        assert len(page2.items) == min(total - 3, 3)
        assert page2.next_offset == (6 if total > 6 else None)

    def test_q_filters_by_partial_name(self, explore_service, db_session):
        _make_group(db_session, name="Jazz Lovers")
        _make_group(db_session, name="Metal Heads")

        page = explore_service.get_explore_groups(q="jazz")
        names = [g.name for g in page.items]
        assert "Jazz Lovers" in names
        assert "Metal Heads" not in names

    def test_q_is_case_insensitive(self, explore_service, db_session):
        _make_group(db_session, name="Bumblebees")

        page = explore_service.get_explore_groups(q="BUMBLEBEE")
        assert any(g.name == "Bumblebees" for g in page.items)

    def test_group_type_bot_returns_only_global(self, explore_service, db_session):
        bot = _make_group(db_session, name="Bot Group", is_global=True)
        human = _make_group(db_session, name="Human Group", is_global=False)

        page = explore_service.get_explore_groups(group_type="bot")
        ids = [g.id for g in page.items]
        assert bot.id in ids
        assert human.id not in ids

    def test_group_type_human_excludes_global(self, explore_service, db_session):
        _make_group(db_session, name="Bot Group", is_global=True)
        human = _make_group(db_session, name="Human Group", is_global=False)

        page = explore_service.get_explore_groups(group_type="human")
        ids = [g.id for g in page.items]
        assert human.id in ids
        assert all(not g.is_global for g in page.items)

    def test_group_type_all_includes_both(self, explore_service, db_session):
        bot = _make_group(db_session, name="Bot Group", is_global=True)
        human = _make_group(db_session, name="Human Group", is_global=False)

        page = explore_service.get_explore_groups(group_type="all")
        ids = [g.id for g in page.items]
        assert bot.id in ids
        assert human.id in ids

    def test_member_count(self, explore_service, db_session, sample_user):
        from app.models.group import group_members
        group = _make_group(db_session, name="With Member")
        db_session.execute(
            group_members.insert().values(group_id=group.id, user_id=sample_user.id, role="member")
        )
        db_session.commit()

        page = explore_service.get_explore_groups()
        item = next(g for g in page.items if g.id == group.id)
        assert item.member_count == 1


# ==================== get_site_stats ====================


class TestGetSiteStats:
    def test_totals_empty_db(self, explore_service):
        stats = explore_service.get_site_stats()
        assert stats.total_albums_nominated == 0
        assert stats.total_reviews == 0
        assert stats.total_active_groups == 0
        assert stats.total_active_members == 0

    def test_total_albums_nominated(self, explore_service, db_session):
        group = _make_group(db_session, name="G1")
        album = _make_album(db_session, title="T1", artist="A")
        _nominate(db_session, group=group, album=album)

        stats = explore_service.get_site_stats()
        assert stats.total_albums_nominated == 1

    def test_total_albums_nominated_counts_distinct(self, explore_service, db_session):
        """Same album in two groups counts as 1 distinct album."""
        g1 = _make_group(db_session, name="G1")
        g2 = _make_group(db_session, name="G2")
        album = _make_album(db_session, title="T1", artist="A")
        _nominate(db_session, group=g1, album=album)
        _nominate(db_session, group=g2, album=album)

        stats = explore_service.get_site_stats()
        assert stats.total_albums_nominated == 1

    def test_total_reviews_excludes_drafts(self, explore_service, db_session, sample_user):
        from app.models.user import User

        group = _make_group(db_session, name="G1")
        album = _make_album(db_session, title="T", artist="A")
        _nominate(db_session, group=group, album=album)
        _review(db_session, album=album, user_id=sample_user.id, rating=8.0)

        # second user for the draft (unique constraint on user_id + album_id)
        user2 = User(email="drafter@test.com", username="drafter", password_hash="x")
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)
        _review(db_session, album=album, user_id=user2.id, rating=6.0, is_draft=True)

        stats = explore_service.get_site_stats()
        assert stats.total_reviews == 1

    def test_top_and_bottom_rated_require_min_reviews(self, explore_service, db_session, sample_user):
        """Albums with fewer than 3 reviews must not appear in top/bottom rated."""
        group = _make_group(db_session, name="G1")
        album = _make_album(db_session, title="Few Reviews", artist="A")
        _nominate(db_session, group=group, album=album)
        _review(db_session, album=album, user_id=sample_user.id, rating=10.0)

        stats = explore_service.get_site_stats()
        ids_top = [a.id for a in stats.top_rated_albums]
        ids_bot = [a.id for a in stats.bottom_rated_albums]
        assert album.id not in ids_top
        assert album.id not in ids_bot

    def test_most_nominated_artists(self, explore_service, db_session):
        group = _make_group(db_session, name="G1")
        a1 = _make_album(db_session, title="T1", artist="The Beatles")
        a2 = _make_album(db_session, title="T2", artist="The Beatles")
        a3 = _make_album(db_session, title="T3", artist="Miles Davis")
        _nominate(db_session, group=group, album=a1)
        _nominate(db_session, group=group, album=a2)
        _nominate(db_session, group=group, album=a3)

        stats = explore_service.get_site_stats()
        artist_names = [a.artist for a in stats.most_nominated_artists]
        assert "The Beatles" in artist_names
        beatles = next(a for a in stats.most_nominated_artists if a.artist == "The Beatles")
        assert beatles.nomination_count == 2
        assert beatles.unique_albums == 2

    def test_most_nominated_albums(self, explore_service, db_session):
        g1 = _make_group(db_session, name="G1")
        g2 = _make_group(db_session, name="G2")
        popular = _make_album(db_session, title="Popular", artist="X")
        niche = _make_album(db_session, title="Niche", artist="Y")
        _nominate(db_session, group=g1, album=popular)
        _nominate(db_session, group=g2, album=popular)
        _nominate(db_session, group=g1, album=niche)

        stats = explore_service.get_site_stats()
        assert stats.most_nominated_albums[0].id == popular.id
        assert stats.most_nominated_albums[0].nomination_count == 2
