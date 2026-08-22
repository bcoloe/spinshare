"""Tests for music service URL detection and ID extraction."""

import pytest
from app.utils.url_parser import (
    MusicService,
    coerce_album_identifier,
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

    def test_intl_locale_url(self):
        # Spotify prefixes a locale segment for non-English clients.
        assert extract_spotify_album_id("https://open.spotify.com/intl-de/album/abc123") == "abc123"

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


class TestCoerceAlbumIdentifier:
    def test_full_spotify_url(self):
        assert (
            coerce_album_identifier(
                MusicService.Spotify, "https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR"
            )
            == "3v1nspBDZhlcJGDW6fUJQR"
        )

    def test_spotify_url_with_tracking_param(self):
        assert (
            coerce_album_identifier(
                MusicService.Spotify,
                "https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR?si=6f2aaf776e7a4eab",
            )
            == "3v1nspBDZhlcJGDW6fUJQR"
        )

    def test_spotify_intl_locale_url(self):
        assert (
            coerce_album_identifier(
                MusicService.Spotify,
                "https://open.spotify.com/intl-de/album/3v1nspBDZhlcJGDW6fUJQR?si=abc",
            )
            == "3v1nspBDZhlcJGDW6fUJQR"
        )

    def test_bare_spotify_id_passes_through(self):
        assert (
            coerce_album_identifier(MusicService.Spotify, "3v1nspBDZhlcJGDW6fUJQR")
            == "3v1nspBDZhlcJGDW6fUJQR"
        )

    def test_surrounding_whitespace_is_stripped(self):
        assert (
            coerce_album_identifier(MusicService.Spotify, "  3v1nspBDZhlcJGDW6fUJQR  ")
            == "3v1nspBDZhlcJGDW6fUJQR"
        )

    def test_apple_music_url_with_title_slug(self):
        assert (
            coerce_album_identifier(
                MusicService.AppleMusic, "https://music.apple.com/us/album/ok-computer/1097862703"
            )
            == "1097862703"
        )

    def test_bare_apple_music_id_passes_through(self):
        assert coerce_album_identifier(MusicService.AppleMusic, "1097862703") == "1097862703"

    def test_youtube_music_browse_url(self):
        assert (
            coerce_album_identifier(
                MusicService.YouTubeMusic, "https://music.youtube.com/browse/MPREb_abc123"
            )
            == "MPREb_abc123"
        )

    def test_youtube_music_playlist_url(self):
        assert (
            coerce_album_identifier(
                MusicService.YouTubeMusic,
                "https://music.youtube.com/playlist?list=OLAK5uy_xyz",
            )
            == "OLAK5uy_xyz"
        )

    def test_cross_service_paste_names_the_right_field(self):
        with pytest.raises(ValueError, match="Apple Music"):
            coerce_album_identifier(
                MusicService.Spotify, "https://music.apple.com/us/album/ok-computer/1097862703"
            )

    def test_wrong_path_on_right_host_raises(self):
        with pytest.raises(ValueError, match="Could not find an album ID"):
            coerce_album_identifier(
                MusicService.Spotify, "https://open.spotify.com/track/3v1nspBDZhlcJGDW6fUJQR"
            )

    def test_bare_value_of_wrong_shape_raises(self):
        # Apple Music IDs are numeric; a base62 Spotify ID is not one.
        with pytest.raises(ValueError, match="Not a valid Apple Music"):
            coerce_album_identifier(MusicService.AppleMusic, "3v1nspBDZhlcJGDW6fUJQR")

    @pytest.mark.parametrize("junk", ["not an id", "some/path", "abc!def"])
    def test_bare_value_with_junk_characters_raises(self, junk):
        with pytest.raises(ValueError, match="Not a valid Spotify"):
            coerce_album_identifier(MusicService.Spotify, junk)

    def test_opaque_legacy_style_id_is_accepted(self):
        # Identifiers stored by earlier code paths aren't all strict base62.
        assert coerce_album_identifier(MusicService.Spotify, "spotify_xyz") == "spotify_xyz"

    def test_empty_value_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            coerce_album_identifier(MusicService.Spotify, "   ")

    def test_bandcamp_is_not_id_based(self):
        with pytest.raises(ValueError, match="full URLs"):
            coerce_album_identifier(MusicService.Bandcamp, "https://artist.bandcamp.com/album/x")
