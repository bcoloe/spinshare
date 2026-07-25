"""Tests for the Wikipedia client utility."""

from unittest.mock import MagicMock, patch

from app.utils.wikipedia_client import (
    _normalize_page_title,
    _page_url,
    find_wikipedia_url,
)


def _make_search_response(titles: list[str], success: bool = True) -> MagicMock:
    """Build a mock MediaWiki search response returning the given page titles."""
    resp = MagicMock()
    resp.is_success = success
    resp.status_code = 200 if success else 500
    resp.json.return_value = {"query": {"search": [{"title": t} for t in titles]}}
    return resp


# ==================== NORMALIZATION / URL HELPERS ====================


class TestNormalizePageTitle:
    def test_strips_disambiguation_parenthetical(self):
        assert _normalize_page_title("Thriller (album)") == "thriller"

    def test_strips_artist_qualified_parenthetical(self):
        assert _normalize_page_title("1989 (Taylor Swift album)") == "1989"

    def test_strips_diacritics_and_punctuation(self):
        assert _normalize_page_title("Björk!") == "bjork"


class TestPageUrl:
    def test_spaces_become_underscores(self):
        assert _page_url("In Rainbows") == "https://en.wikipedia.org/wiki/In_Rainbows"

    def test_parentheses_are_percent_encoded(self):
        assert _page_url("1989 (album)") == "https://en.wikipedia.org/wiki/1989_%28album%29"


# ==================== FIND WIKIPEDIA URL ====================


class TestFindWikipediaUrl:
    def test_returns_album_page_when_title_matches(self):
        resp = _make_search_response(["In Rainbows", "Radiohead"])
        with patch("httpx.get", return_value=resp) as mock_get:
            url = find_wikipedia_url("In Rainbows", "Radiohead")
        assert url == "https://en.wikipedia.org/wiki/In_Rainbows"
        # Album match should short-circuit before the artist search.
        mock_get.assert_called_once()

    def test_falls_back_to_artist_page(self):
        album_resp = _make_search_response(["Some Unrelated Article"])
        artist_resp = _make_search_response(["Radiohead"])
        with patch("httpx.get", side_effect=[album_resp, artist_resp]):
            url = find_wikipedia_url("Obscure Bootleg", "Radiohead")
        assert url == "https://en.wikipedia.org/wiki/Radiohead"

    def test_returns_none_when_nothing_clears_threshold(self):
        album_resp = _make_search_response(["Totally Different Thing"])
        artist_resp = _make_search_response(["Some Other Band Entirely"])
        with patch("httpx.get", side_effect=[album_resp, artist_resp]):
            url = find_wikipedia_url("Obscure Bootleg", "Radiohead")
        assert url is None

    def test_returns_none_on_empty_results(self):
        with patch("httpx.get", return_value=_make_search_response([])):
            assert find_wikipedia_url("Anything", "Anyone") is None

    def test_returns_none_on_http_error(self):
        with patch("httpx.get", return_value=_make_search_response([], success=False)):
            assert find_wikipedia_url("Anything", "Anyone") is None

    def test_returns_none_and_never_raises_on_network_error(self):
        with patch("httpx.get", side_effect=Exception("network down")):
            # Must not propagate — safe as a background task.
            assert find_wikipedia_url("Anything", "Anyone") is None

    def test_prefers_album_over_artist_when_both_would_match(self):
        # Album search already yields a strong album match; artist search must not run.
        resp = _make_search_response(["OK Computer"])
        with patch("httpx.get", return_value=resp) as mock_get:
            url = find_wikipedia_url("OK Computer", "Radiohead")
        assert url == "https://en.wikipedia.org/wiki/OK_Computer"
        mock_get.assert_called_once()
