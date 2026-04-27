# backend/app/utils/spotify_client_test.py
#
# Unit tests for spotify_client helpers. HTTP calls are mocked so these run
# without credentials.

from unittest.mock import MagicMock, patch

import pytest

from app.utils.spotify_client import _normalized_title, search_albums


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

    def _mock_search_response(self, items: list[dict]):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"albums": {"items": items}}
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
            results = search_albums("OK Computer")

        assert len(results) == 1
        assert results[0].spotify_album_id == "id1"

    def test_keeps_distinct_albums(self):
        items = [
            self._make_item("id1", "OK Computer", "Radiohead"),
            self._make_item("id2", "The Bends", "Radiohead"),
        ]
        mock_resp = self._mock_search_response(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_resp):
            results = search_albums("radiohead")

        assert len(results) == 2

    def test_keeps_same_title_different_artist(self):
        items = [
            self._make_item("id1", "Greatest Hits", "Artist A"),
            self._make_item("id2", "Greatest Hits", "Artist B"),
        ]
        mock_resp = self._mock_search_response(items)

        with patch("app.utils.spotify_client._get_client_token", return_value="tok"), \
             patch("httpx.get", return_value=mock_resp):
            results = search_albums("greatest hits")

        assert len(results) == 2
