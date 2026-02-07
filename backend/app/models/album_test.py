"""Unit tests of Album model."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Album


class TestAlbumModel:
    def test_create_album(self, db_session):
        """Test creating an album."""
        album = Album(
            spotify_album_id="spotify_123",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05",
            cover_url="https://example.com/cover.jpg",
        )
        db_session.add(album)
        db_session.commit()

        assert album.id is not None
        assert album.spotify_album_id == "spotify_123"
        assert album.title == "OK Computer"
        assert album.artist == "Radiohead"
        assert album.release_date == "1997-05"
        assert album.cover_url == "https://example.com/cover.jpg"
        assert album.added_at is not None

    def test_similar_album_allowed(self, db_session):
        album = Album(
            spotify_album_id="spotify_123",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05",
            cover_url="https://example.com/cover.jpg",
        )
        db_session.add(album)
        db_session.commit()

        assert album.id is not None
        assert album.spotify_album_id == "spotify_123"
        assert album.title == "OK Computer"
        assert album.artist == "Radiohead"
        assert album.release_date == "1997-05"
        assert album.cover_url == "https://example.com/cover.jpg"
        assert album.added_at is not None

        # Test nearly identical albums with different album ID
        another_album = Album(
            spotify_album_id="spotify_456",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05",
            cover_url="https://example.com/cover.jpg",
        )
        db_session.add(another_album)
        db_session.commit()

        assert another_album.id is not None
        assert another_album.spotify_album_id == "spotify_456"
        assert another_album.title == "OK Computer"
        assert another_album.artist == "Radiohead"
        assert another_album.release_date == "1997-05"
        assert another_album.cover_url == "https://example.com/cover.jpg"
        assert another_album.added_at is not None

    def test_unique_spotify_id(self, db_session):
        """Test that multiple identical album IDs can't be submitted."""
        album = Album(
            spotify_album_id="spotify_123",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05",
            cover_url="https://example.com/cover.jpg",
        )
        db_session.add(album)
        db_session.commit()

        # Test nearly identical albums with different album ID
        another_album = Album(
            spotify_album_id="spotify_123",
            title="OK Computer-ish",
            artist="Radioheads",
            release_date="1997-05",
            cover_url="https://example.com/cover.jpg",
        )
        db_session.add(another_album)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_album_persists_to_database(self, db_session, sample_album):
        """Test that album data is actually saved to and retrievable from database"""
        album_id = sample_album.id

        # Close the session and create a new one to simulate new request.
        db_session.close()

        # Query in fresh session
        fresh_album = db_session.query(Album).filter(Album.id == album_id).first()

        assert fresh_album is not None
        assert fresh_album.spotify_album_id == "spotify_123"
        assert fresh_album.title == "OK Computer"
        assert fresh_album.artist == "Radiohead"
        assert fresh_album.release_date == "1997-05"
        assert fresh_album.cover_url == "https://example.com/cover.jpg"
        assert fresh_album.added_at is not None
