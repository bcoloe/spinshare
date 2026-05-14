# backend/app/utils/spotify_client_test.py
#
# Unit tests for spotify_client helpers. HTTP calls are mocked so these run
# without credentials.

from unittest.mock import MagicMock, call, patch

import pytest

from app.utils.spotify_client import _normalized_title, get_albums_batch, search_albums


class TestNormalizedTitle:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("OK Computer", "ok computer"),
            ("OK Computer (Remastered)", "ok computer"),
            ("OK Computer - Remastered", "ok computer"),
            ("OK Computer (Remastered 2017)", "ok computer"),
            ("OK Computer (2017 Remastered)", "ok computer"),
            ("OK Computer (Deluxe Edition)", "ok computer"),
            ("OK Computer (Deluxe)", "ok computer"),
            ("OK Computer (Bonus Tracks)", "ok computer"),
            ("OK Computer (Anniversary Edition)", "ok computer"),
            ("OK Computer (Expanded Edition)", "ok computer"),
            ("OK Computer (Special Edition)", "ok computer"),
            ("OK Computer (Super Deluxe Edition)", "ok computer"),
            # Should NOT strip — these are not edition markers
            ("Live at the Apollo", "live at the apollo"),
            ("The Dark Side of the Moon", "the dark side of the moon"),
        ],
    )
    def test_strip_edition_suffixes(self, raw, expected):
        assert _normalized_title(raw) == expected


class TestSearchAlbumsDeduplication:
    def _make_item(self, id: str, name: str, artist: str) -> dict:
        return {
            "id": id,
            "name": name,
            "artists": [{"name": artist}],
            "release_date": "1997-05-21",
            "images": [],
            "genres": [],
        }

    def _mock_search_response(self, items: list[dict], total: int | None = None):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"albums": {"items": items, "total": total if total is not None else len(items)}}
        return mock_resp

    def test_deduplicates_remastered_variant(self):
        items = [
            self._make_item("id1", "OK Computer", "Radiohead"),
            self._make_item("id2", "OK Computer (Remastered)", "Radiohead"),
            self._make_item("id3", "OK Computer (Deluxe Edition)", "Radiohead"),
        ]
        mock_resp = self._mock_search_response(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_resp):
            page = search_albums("OK Computer")

        assert len(page.items) == 1
        assert page.items[0].spotify_album_id == "id1"

    def test_keeps_distinct_albums(self):
        items = [
            self._make_item("id1", "OK Computer", "Radiohead"),
            self._make_item("id2", "The Bends", "Radiohead"),
        ]
        mock_resp = self._mock_search_response(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_resp):
            page = search_albums("radiohead")

        assert len(page.items) == 2

    def test_keeps_same_title_different_artist(self):
        items = [
            self._make_item("id1", "Greatest Hits", "Artist A"),
            self._make_item("id2", "Greatest Hits", "Artist B"),
        ]
        mock_resp = self._mock_search_response(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_resp):
            page = search_albums("greatest hits")

        assert len(page.items) == 2


class TestSearchAlbumsMaxRetryAfter:
    def _make_429(self, retry_after: int) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 429
        mock.is_success = False
        mock.headers = {"Retry-After": str(retry_after)}
        return mock

    def _make_200(self) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 200
        mock.is_success = True
        mock.json.return_value = {"albums": {"items": [], "total": 0}}
        return mock

    def test_short_max_retry_after_aborts_fast(self):
        """Retry-After (15s) exceeds max_retry_after (10s) → raises 429 immediately without sleeping."""
        mock_429 = self._make_429(retry_after=15)
        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_429), \
             patch("time.sleep") as mock_sleep:
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                search_albums("test", max_retry_after=10)
            assert exc_info.value.status_code == 429
            mock_sleep.assert_not_called()

    def test_long_max_retry_after_waits_and_retries(self):
        """Retry-After (10s) is within max_retry_after (60s) → sleeps and retries successfully."""
        mock_429 = self._make_429(retry_after=10)
        mock_200 = self._make_200()
        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", side_effect=[mock_429, mock_200]), \
             patch("time.sleep") as mock_sleep:
            page = search_albums("test", max_retry_after=60)
            mock_sleep.assert_called_once_with(10)
            assert page.items == []

    def test_exhausted_retries_raise_429_not_502(self):
        """All 3 retries return 429 (within threshold) → final raise is 429, not 502."""
        mock_429 = self._make_429(retry_after=1)
        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_429), \
             patch("time.sleep"):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                search_albums("test", max_retry_after=60)
            assert exc_info.value.status_code == 429


class TestGetAlbumsBatch:
    def _make_item(self, id: str, name: str, artist: str) -> dict:
        return {
            "id": id,
            "name": name,
            "artists": [{"name": artist}],
            "release_date": "2020-01-01",
            "images": [{"url": f"https://example.com/{id}.jpg"}],
            "genres": ["rock"],
        }

    def _make_200(self, items: list) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 200
        mock.is_success = True
        mock.json.return_value = {"albums": items}
        return mock

    def _make_429(self, retry_after: int = 1) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 429
        mock.is_success = False
        mock.headers = {"Retry-After": str(retry_after)}
        return mock

    def test_empty_ids_returns_empty(self):
        results = get_albums_batch([])
        assert results == []

    def test_single_chunk_one_call(self):
        ids = [f"id{i}" for i in range(5)]
        items = [self._make_item(id, f"Album {id}", "Artist") for id in ids]
        mock_200 = self._make_200(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_200) as mock_get:
            results = get_albums_batch(ids)

        assert mock_get.call_count == 1
        assert len(results) == 5

    def test_multi_chunk_two_calls(self):
        ids = [f"id{i}" for i in range(21)]
        chunk1_items = [self._make_item(f"id{i}", f"Album {i}", "Artist") for i in range(20)]
        chunk2_items = [self._make_item("id20", "Album 20", "Artist")]
        mock_1 = self._make_200(chunk1_items)
        mock_2 = self._make_200(chunk2_items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", side_effect=[mock_1, mock_2]) as mock_get:
            results = get_albums_batch(ids)

        assert mock_get.call_count == 2
        assert len(results) == 21

    def test_skips_null_items(self):
        items = [self._make_item("id1", "Album 1", "Artist"), None, self._make_item("id3", "Album 3", "Artist")]
        mock_200 = self._make_200(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_200):
            results = get_albums_batch(["id1", "bad_id", "id3"])

        assert len(results) == 2
        assert results[0].spotify_album_id == "id1"
        assert results[1].spotify_album_id == "id3"

    def test_retries_on_429_then_succeeds(self):
        items = [self._make_item("id1", "Album 1", "Artist")]
        mock_429 = self._make_429(retry_after=1)
        mock_200 = self._make_200(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", side_effect=[mock_429, mock_200]), \
             patch("time.sleep") as mock_sleep:
            results = get_albums_batch(["id1"])

        mock_sleep.assert_called_once_with(1)
        assert len(results) == 1
