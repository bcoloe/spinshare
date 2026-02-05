"""Unit tests of inter-table relationships."""

from app.models import SpotifyConnection, User


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
