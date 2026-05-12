"""Tests for YouTube Music client utility."""

from unittest.mock import MagicMock, patch

from app.utils.ytmusic_client import search_album_browse_id


class TestSearchAlbumBrowseId:
    def test_returns_browse_id_on_match(self):
        mock_results = [{"browseId": "MPREb_abc123", "title": "OK Computer"}]
        with patch("app.utils.ytmusic_client.YTMusic") as MockYTMusic:
            MockYTMusic.return_value.search.return_value = mock_results
            result = search_album_browse_id("OK Computer", "Radiohead")
        assert result == "MPREb_abc123"
        MockYTMusic.return_value.search.assert_called_once_with(
            "Radiohead OK Computer", filter="albums", limit=1
        )

    def test_returns_none_on_empty_results(self):
        with patch("app.utils.ytmusic_client.YTMusic") as MockYTMusic:
            MockYTMusic.return_value.search.return_value = []
            result = search_album_browse_id("Unknown Album", "Unknown Artist")
        assert result is None

    def test_returns_none_when_browse_id_missing(self):
        mock_results = [{"title": "Some Album"}]  # no browseId key
        with patch("app.utils.ytmusic_client.YTMusic") as MockYTMusic:
            MockYTMusic.return_value.search.return_value = mock_results
            result = search_album_browse_id("Some Album", "Some Artist")
        assert result is None

    def test_propagates_exception(self):
        with patch("app.utils.ytmusic_client.YTMusic") as MockYTMusic:
            MockYTMusic.return_value.search.side_effect = Exception("network error")
            try:
                search_album_browse_id("Title", "Artist")
                assert False, "expected exception"
            except Exception as e:
                assert "network error" in str(e)
