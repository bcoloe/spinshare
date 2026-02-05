"""Unit tests of inter-table relationships."""

from sqlalchemy.exc import IntegrityError

from app.models import Genre, Group, SpotifyConnection, User


class TestUserModelRelationships:
    def test_user_spotify_connection(self, db_session, sample_user: User):
        """Test one-to-one relationship between User and SpotifyConnection."""
        # There should be no relation at start.
        assert sample_user.spotify_connection is None

        spotify = SpotifyConnection(
            user_id=sample_user.id,
            spotify_user_id="spotify_123",
            access_token="token",
            refresh_token="refresh",
        )
        db_session.add(spotify)
        db_session.commit()

        # Test relationship from User side.
        assert sample_user.spotify_connection is not None
        assert sample_user.spotify_connection.spotify_user_id == "spotify_123"

        # Test relationship from SpotifyConnection side.
        assert spotify.user.id == sample_user.id


class TestAlbumModelRelationships:
    def test_album_genres(self, db_session, sample_album, sample_genre):
        sample_album.genres.append(sample_genre)

        assert sample_album in sample_genre.albums
        assert sample_genre in sample_album.genres

        # Now add other genres and confirm presence
        genre_pop = Genre(name="pop")
        genre_rap = Genre(name="rap")
        db_session.add_all([genre_pop, genre_rap])
        db_session.commit()

        sample_album.genres.append(genre_pop)
        assert sample_album in sample_genre.albums
        assert sample_album in genre_pop.albums
        assert sample_album not in genre_rap.albums
        assert sample_genre in sample_album.genres
        assert genre_pop in sample_album.genres
        assert genre_rap not in sample_album.genres


class TestGroupRelationships:
    def test_group_members(self, db_session, creators):
        """Test many-to-many relationship between Group and Users"""
        users = creators.users(["foo", "bar", "baz"])

        # Create group and add users.
        group = Group(name="Test Group", created_by=users[0].id)
        for user in users:
            group.members.append(user)
        db_session.add(group)
        db_session.commit()

        assert len(group.members) == len(users)
        for user in users:
            assert user in group.members
            assert group in user.groups

    def test_group_creator(self, db_session, sample_user):
        group = Group(name="My Group", created_by=sample_user.id)
        db_session.add(group)
        db_session.commit()

        assert group.creator.id == sample_user.id
        assert group in sample_user.created_groups


class TestGroupAlbumRelationships:
    def test_group_albums(self, sample_album, creators):
        """Test that group albums are reflected in group, user, and album associations."""
        users = creators.users([f"user{x}" for x in range(3)])
        group = creators.group(name="Test Group", creator=users[0])
        group_album = creators.group_album(group, sample_album, users[0])

        assert group_album in group.albums
        assert group_album in users[0].added_albums
        assert group_album in sample_album.group_albums

    def test_unique_user_album_per_group(self, creators, sample_album):
        """Test that the same user can't add the same album twice to the same group"""
        users = creators.users([f"user{x}" for x in range(3)])
        group1 = creators.group(name="Test Group 1", creator=users[0])

        # Ensure user cannot add to same group multiple times.
        creators.group_album(group1, sample_album, users[0])
        creators.group_album(group1, sample_album, users[0], exception=IntegrityError)

    def test_same_user_album_multiple_groups(self, creators, sample_album):
        """Test that the same user can nominate the same album to multiple groups."""
        users = creators.users([f"user{x}" for x in range(3)])
        group1 = creators.group(name="Test Group 1", creator=users[0])
        group2 = creators.group(name="Test Group 2", creator=users[1])

        creators.group_album(group1, sample_album, users[0])
        creators.group_album(group2, sample_album, users[0])

    def test_same_group_album_multiple_users(self, creators, sample_album):
        """Test that multiple group members can add the same album."""
        users = creators.users([f"user{x}" for x in range(3)])
        group1 = creators.group(name="Test Group 1", creator=users[0])

        # Ensure other user can add same album.
        creators.group_album(group1, sample_album, users[0])
        creators.group_album(group1, sample_album, users[1])


class TestAlbumReviewRelationships:
    def test_album_reviews(self, sample_album, creators):
        """Test one-to-many relationship between Album and Reviews."""
        users = creators.users([f"user{x}" for x in range(3)])

        review1 = creators.review(users[0], sample_album, 9)
        review2 = creators.review(users[1], sample_album, 7)

        assert len(sample_album.reviews) == 2
        assert review1 in users[0].reviews
        assert review2 in users[1].reviews
