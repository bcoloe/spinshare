"""Tests for pitchfork_bot._process_album."""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")

from app.utils.pitchfork_scraper import PitchforkAlbum
from app.utils.spotify_client import SpotifyAlbumResult
from bots.pitchfork_bot import _process_album


def _make_pitchfork_album(artist="Radiohead", title="Kid A") -> PitchforkAlbum:
    return PitchforkAlbum(artist=artist, title=title, review_url="https://pitchfork.com/review/1")


def _make_spotify_result(artist="Radiohead", title="Kid A", spotify_id="spotify_123") -> SpotifyAlbumResult:
    return SpotifyAlbumResult(
        spotify_album_id=spotify_id,
        title=title,
        artist=artist,
        release_date="2000-10-02",
        cover_url="https://example.com/cover.jpg",
        genres=["electronic"],
    )


def _make_album_mock(id=1, title="Kid A", artist="Radiohead"):
    album = MagicMock()
    album.id = id
    album.title = title
    album.artist = artist
    return album


class TestProcessAlbumDbCache:
    def test_skips_spotify_when_album_in_db(self):
        """When album is already in DB, search_albums must not be called."""
        cached_album = _make_album_mock()
        album_svc = MagicMock()
        album_svc.get_album_by_title_artist.return_value = cached_album
        album_svc.nominate_album.return_value = MagicMock()

        with patch("bots.pitchfork_bot.search_albums") as mock_search:
            result = _process_album(
                _make_pitchfork_album(),
                bot_user=MagicMock(),
                group_id=1,
                album_svc=album_svc,
                dry_run=False,
            )

        mock_search.assert_not_called()
        assert result == "nominated"

    def test_calls_spotify_when_not_in_db(self):
        """When album is absent from DB, search_albums must be called."""
        spotify_result = _make_spotify_result()
        created_album = _make_album_mock()
        album_svc = MagicMock()
        album_svc.get_album_by_title_artist.return_value = None
        album_svc.get_or_create_album.return_value = created_album
        album_svc.nominate_album.return_value = MagicMock()

        with patch("bots.pitchfork_bot.search_albums", return_value=[spotify_result]) as mock_search:
            result = _process_album(
                _make_pitchfork_album(),
                bot_user=MagicMock(),
                group_id=1,
                album_svc=album_svc,
                dry_run=False,
            )

        mock_search.assert_called_once_with(
            artist="Radiohead",
            album="Kid A",
            limit=1,
            max_retry_after=60,
        )
        assert result == "nominated"

    def test_dry_run_with_db_cache_returns_dry_run(self):
        """Dry-run path with cached album returns 'dry_run' and does not nominate."""
        cached_album = _make_album_mock()
        album_svc = MagicMock()
        album_svc.get_album_by_title_artist.return_value = cached_album

        with patch("bots.pitchfork_bot.search_albums") as mock_search:
            result = _process_album(
                _make_pitchfork_album(),
                bot_user=MagicMock(),
                group_id=1,
                album_svc=album_svc,
                dry_run=True,
            )

        mock_search.assert_not_called()
        album_svc.nominate_album.assert_not_called()
        assert result == "dry_run"

    def test_dry_run_without_db_calls_spotify_but_does_not_nominate(self):
        spotify_result = _make_spotify_result()
        album_svc = MagicMock()
        album_svc.get_album_by_title_artist.return_value = None

        with patch("bots.pitchfork_bot.search_albums", return_value=[spotify_result]):
            result = _process_album(
                _make_pitchfork_album(),
                bot_user=MagicMock(),
                group_id=1,
                album_svc=album_svc,
                dry_run=True,
            )

        album_svc.nominate_album.assert_not_called()
        assert result == "dry_run"

    def test_no_spotify_match_returns_no_match(self):
        album_svc = MagicMock()
        album_svc.get_album_by_title_artist.return_value = None

        with patch("bots.pitchfork_bot.search_albums", return_value=[]):
            result = _process_album(
                _make_pitchfork_album(),
                bot_user=MagicMock(),
                group_id=1,
                album_svc=album_svc,
                dry_run=False,
            )

        assert result == "no_match"

    def test_spotify_error_returns_error(self):
        from fastapi import HTTPException, status

        album_svc = MagicMock()
        album_svc.get_album_by_title_artist.return_value = None

        with patch(
            "bots.pitchfork_bot.search_albums",
            side_effect=HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limited"),
        ):
            result = _process_album(
                _make_pitchfork_album(),
                bot_user=MagicMock(),
                group_id=1,
                album_svc=album_svc,
                dry_run=False,
            )

        assert result == "error"

    def test_already_nominated_returns_skipped(self):
        from fastapi import HTTPException, status

        cached_album = _make_album_mock()
        album_svc = MagicMock()
        album_svc.get_album_by_title_artist.return_value = cached_album
        album_svc.nominate_album.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already nominated"
        )

        with patch("bots.pitchfork_bot.search_albums"):
            result = _process_album(
                _make_pitchfork_album(),
                bot_user=MagicMock(),
                group_id=1,
                album_svc=album_svc,
                dry_run=False,
            )

        assert result == "skipped"
