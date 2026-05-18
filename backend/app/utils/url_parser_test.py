"""Tests for music service URL detection and ID extraction."""

import pytest
from app.utils.url_parser import (
    MusicService,
    detect_service,
    extract_apple_music_album_id,
    extract_spotify_album_id,
    extract_youtube_music_id,
)


class TestDetectService:
    def test_spotify_url(self):
        assert detect_service("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy") == MusicService.Spotify

    def test_spotify_url_with_query_params(self):
        assert detect_service("https://open.spotify.com/album/abc123?si=xyz") == MusicService.Spotify

    def test_apple_music_url(self):
        assert detect_service("https://music.apple.com/us/album/ok-computer/1097862703") == MusicService.AppleMusic

    def test_apple_music_url_no_slug(self):
        assert detect_service("https://music.apple.com/us/album/1097862703") == MusicService.AppleMusic

    def test_youtube_music_url_browse(self):
        assert detect_service("https://music.youtube.com/browse/MPREb_abc123") == MusicService.YouTubeMusic

    def test_youtube_music_url_playlist(self):
        assert detect_service("https://music.youtube.com/playlist?list=OLAK5uy_abc") == MusicService.YouTubeMusic

    def test_bandcamp_url_subdomain(self):
        assert detect_service("https://radiohead.bandcamp.com/album/kid-a") == MusicService.Bandcamp

    def test_bandcamp_url_root_domain(self):
        assert detect_service("https://bandcamp.com/") == MusicService.Bandcamp

    def test_unrecognized_url(self):
        assert detect_service("https://soundcloud.com/artist/album") is None

    def test_regular_youtube_url(self):
        assert detect_service("https://www.youtube.com/watch?v=abc") is None

    def test_empty_string(self):
        assert detect_service("") is None


class TestExtractSpotifyAlbumId:
    def test_standard_url(self):
        assert extract_spotify_album_id("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy") == "4aawyAB9vmqN3uQ7FjRGTy"

    def test_url_with_query_params(self):
        assert extract_spotify_album_id("https://open.spotify.com/album/abc123def456?si=xyz") == "abc123def456"

    def test_url_with_trailing_slash(self):
        assert extract_spotify_album_id("https://open.spotify.com/album/abc123/") == "abc123"

    def test_non_album_path_returns_none(self):
        assert extract_spotify_album_id("https://open.spotify.com/track/abc123") is None

    def test_no_id_in_path_returns_none(self):
        assert extract_spotify_album_id("https://open.spotify.com/album/") is None


class TestExtractAppleMusicAlbumId:
    def test_url_with_title_slug(self):
        assert extract_apple_music_album_id("https://music.apple.com/us/album/ok-computer/1097862703") == "1097862703"

    def test_url_without_title_slug(self):
        assert extract_apple_music_album_id("https://music.apple.com/us/album/1097862703") == "1097862703"

    def test_url_with_query_params(self):
        assert extract_apple_music_album_id("https://music.apple.com/us/album/ok-computer/1097862703?i=123") == "1097862703"

    def test_non_numeric_path_returns_none(self):
        assert extract_apple_music_album_id("https://music.apple.com/us/artist/radiohead") is None

    def test_url_picks_last_numeric_segment(self):
        # storefront "123" in path must not be confused with album ID — album ID is last
        result = extract_apple_music_album_id("https://music.apple.com/us/album/some-title/9876543210")
        assert result == "9876543210"


class TestExtractYouTubeMusicId:
    def test_browse_url(self):
        assert extract_youtube_music_id("https://music.youtube.com/browse/MPREb_abc123") == "MPREb_abc123"

    def test_playlist_url(self):
        assert extract_youtube_music_id("https://music.youtube.com/playlist?list=OLAK5uy_abc") == "OLAK5uy_abc"

    def test_browse_url_with_query_params(self):
        assert extract_youtube_music_id("https://music.youtube.com/browse/MPREb_abc?feature=share") == "MPREb_abc"

    def test_non_album_url_returns_none(self):
        assert extract_youtube_music_id("https://music.youtube.com/watch?v=abc") is None

    def test_playlist_without_list_param_returns_none(self):
        assert extract_youtube_music_id("https://music.youtube.com/playlist") is None
