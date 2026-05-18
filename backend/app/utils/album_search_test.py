"""Tests for the album_search merge and normalization utilities."""

import pytest

from app.utils.album_search import UnifiedAlbumResult, merge_search_results, normalize_title_for_dedup
from app.utils.apple_music_client import AppleMusicAlbumResult
from app.utils.spotify_client import SpotifyAlbumResult


def _spotify(spotify_id, title, artist, cover_url=None, genres=None):
    return SpotifyAlbumResult(
        spotify_album_id=spotify_id,
        title=title,
        artist=artist,
        release_date="2024-01-01",
        cover_url=cover_url,
        genres=genres or [],
    )


def _apple(apple_id, title, artist, cover_url=None, genres=None):
    return AppleMusicAlbumResult(
        id=apple_id,
        title=title,
        artist=artist,
        release_date="2024-01-01",
        cover_url=cover_url,
        genres=genres or [],
    )


class TestNormalizeTitleForDedup:
    def test_lowercase(self):
        assert normalize_title_for_dedup("OK Computer") == "ok computer"

    def test_strips_deluxe_edition(self):
        assert normalize_title_for_dedup("In Rainbows (Deluxe Edition)") == "in rainbows"

    def test_strips_remastered(self):
        assert normalize_title_for_dedup("The Bends Remastered") == "the bends"

    def test_strips_trailing_parenthetical(self):
        assert normalize_title_for_dedup("Kid A (Collector's Edition)") == "kid a"

    def test_strips_ep_dash_qualifier(self):
        assert normalize_title_for_dedup("Some Song - EP") == "some song"

    def test_strips_stacked_suffixes(self):
        assert normalize_title_for_dedup("Album - EP (Remastered)") == "album"

    def test_identical_titles_match(self):
        assert normalize_title_for_dedup("OK Computer") == normalize_title_for_dedup("OK Computer")

    def test_edition_variant_matches_plain(self):
        assert normalize_title_for_dedup("In Rainbows Deluxe Edition") == normalize_title_for_dedup("In Rainbows")


class TestMergeSearchResults:
    def test_empty_inputs(self):
        result = merge_search_results([], [])
        assert result == []

    def test_spotify_only_results(self):
        spotify = [_spotify("s1", "OK Computer", "Radiohead")]
        result = merge_search_results(spotify, [])
        assert len(result) == 1
        assert result[0].spotify_album_id == "s1"
        assert result[0].apple_music_album_id is None

    def test_apple_only_results(self):
        apple = [_apple("a1", "OK Computer", "Radiohead")]
        result = merge_search_results([], apple)
        assert len(result) == 1
        assert result[0].spotify_album_id is None
        assert result[0].apple_music_album_id == "a1"

    def test_matched_pair_merges_ids(self):
        spotify = [_spotify("s1", "OK Computer", "Radiohead", cover_url="https://spotify-cover.jpg")]
        apple = [_apple("a1", "OK Computer", "Radiohead", cover_url="https://apple-cover.jpg")]
        result = merge_search_results(spotify, apple)
        assert len(result) == 1
        assert result[0].spotify_album_id == "s1"
        assert result[0].apple_music_album_id == "a1"
        assert result[0].cover_url == "https://spotify-cover.jpg"  # Spotify is primary

    def test_matched_pair_with_edition_variant(self):
        spotify = [_spotify("s1", "In Rainbows (Deluxe Edition)", "Radiohead")]
        apple = [_apple("a1", "In Rainbows", "Radiohead")]
        result = merge_search_results(spotify, apple)
        assert len(result) == 1
        assert result[0].spotify_album_id == "s1"
        assert result[0].apple_music_album_id == "a1"

    def test_ordering_matched_first_then_spotify_then_apple(self):
        spotify = [
            _spotify("s1", "Matched Album", "Artist A"),
            _spotify("s2", "Spotify Only", "Artist B"),
        ]
        apple = [
            _apple("a1", "Matched Album", "Artist A"),
            _apple("a2", "Apple Only", "Artist C"),
        ]
        result = merge_search_results(spotify, apple)
        assert len(result) == 3
        # Matched pair first
        assert result[0].spotify_album_id == "s1"
        assert result[0].apple_music_album_id == "a1"
        # Spotify-only second
        assert result[1].spotify_album_id == "s2"
        assert result[1].apple_music_album_id is None
        # Apple-only last
        assert result[2].spotify_album_id is None
        assert result[2].apple_music_album_id == "a2"

    def test_no_false_positive_match_different_artist(self):
        spotify = [_spotify("s1", "Greatest Hits", "Artist A")]
        apple = [_apple("a1", "Greatest Hits", "Artist B")]
        result = merge_search_results(spotify, apple)
        assert len(result) == 2
        assert result[0].spotify_album_id == "s1"
        assert result[0].apple_music_album_id is None
        assert result[1].spotify_album_id is None
        assert result[1].apple_music_album_id == "a1"

    def test_apple_genre_used_when_spotify_has_none(self):
        spotify = [_spotify("s1", "OK Computer", "Radiohead", genres=[])]
        apple = [_apple("a1", "OK Computer", "Radiohead", genres=["Alternative"])]
        result = merge_search_results(spotify, apple)
        assert result[0].genres == ["Alternative"]

    def test_spotify_genre_preferred_when_both_have_genres(self):
        spotify = [_spotify("s1", "OK Computer", "Radiohead", genres=["art rock"])]
        apple = [_apple("a1", "OK Computer", "Radiohead", genres=["Alternative"])]
        result = merge_search_results(spotify, apple)
        assert result[0].genres == ["art rock"]
