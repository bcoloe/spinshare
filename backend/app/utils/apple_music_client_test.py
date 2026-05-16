"""Tests for Apple Music client utility functions."""

from unittest.mock import MagicMock, patch

import app.utils.apple_music_client as am_client
import pytest
from app.utils.apple_music_client import (
    _artist_similarity,
    _censor_for_search,
    _normalized_title,
    _split_artists,
    find_apple_music_album,
    generate_developer_token,
)
from fastapi import HTTPException

# ==================== GENERATE DEVELOPER TOKEN ====================


class TestGenerateDeveloperToken:
    def setup_method(self):
        am_client._dev_token = None
        am_client._dev_token_expires_at = 0.0

    def test_raises_503_when_not_configured(self):
        mock_settings = MagicMock()
        mock_settings.APPLE_MUSIC_TEAM_ID = ""
        mock_settings.APPLE_MUSIC_KEY_ID = ""
        mock_settings.APPLE_MUSIC_PRIVATE_KEY = ""
        with patch("app.utils.apple_music_client.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                generate_developer_token()
        assert exc_info.value.status_code == 503

    def test_returns_cached_token_when_valid(self):
        am_client._dev_token = "cached_token"
        am_client._dev_token_expires_at = 9_999_999_999.0
        token = generate_developer_token()
        assert token == "cached_token"

    def test_generates_and_caches_new_token(self):
        mock_settings = MagicMock()
        mock_settings.APPLE_MUSIC_TEAM_ID = "TEAM123"
        mock_settings.APPLE_MUSIC_KEY_ID = "KEY456"
        mock_settings.APPLE_MUSIC_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----"

        with patch("app.utils.apple_music_client.get_settings", return_value=mock_settings):
            with patch("jwt.encode", return_value="generated_token") as mock_encode:
                token = generate_developer_token()

        assert token == "generated_token"
        assert am_client._dev_token == "generated_token"
        mock_encode.assert_called_once()
        _, kwargs = mock_encode.call_args
        assert kwargs["algorithm"] == "ES256"
        assert kwargs["headers"]["kid"] == "KEY456"


# ==================== NORMALIZATION HELPERS ====================


class TestNormalizedTitle:
    def test_strips_trailing_parenthetical(self):
        assert _normalized_title("Nevermind (Remastered)") == "nevermind"

    def test_strips_deluxe_edition(self):
        assert _normalized_title("Take Care (Deluxe)") == "take care"

    def test_strips_complex_parenthetical(self):
        result = _normalized_title(
            "In The Court Of The Crimson King (Expanded & Remastered Original Album Mix)"
        )
        assert result == "in the court of the crimson king"

    def test_strips_multiple_trailing_parentheticals(self):
        assert _normalized_title("Nevermind (Super Deluxe) (Remastered)") == "nevermind"

    def test_strips_diacritics(self):
        assert _normalized_title("Café") == "cafe"

    def test_preserves_non_decomposable_chars(self):
        # Ø has no NFKD decomposition, so it stays as ø after lowercasing
        assert _normalized_title("Sysivalo") == "sysivalo"

    def test_no_trailing_paren_left_unchanged(self):
        assert _normalized_title("Nevermind") == "nevermind"

    def test_strips_dash_ep_suffix(self):
        assert _normalized_title("M3LL155X - EP") == "m3ll155x"

    def test_strips_dash_single_suffix(self):
        assert _normalized_title("Waterfall - Single") == "waterfall"

    def test_strips_stacked_dash_and_paren_suffix(self):
        assert _normalized_title("Song Title - EP (Remastered)") == "song title"

    def test_strips_exclamation_mark(self):
        assert _normalized_title("Norman Fucking Rockwell!") == "norman fucking rockwell"

    def test_strips_censorship_asterisks(self):
        # Apple returns "F*****g" with asterisks; stripping them reduces it to "fg"
        result = _normalized_title("Norman F*****g Rockwell!")
        assert result == "norman fg rockwell"

    def test_censored_and_uncensored_title_similar_enough(self):
        # "norman fucking rockwell" vs "norman fg rockwell" must clear _TITLE_THRESHOLD (0.82)
        import difflib
        q = _normalized_title("Norman Fucking Rockwell!")
        c = _normalized_title("Norman F*****g Rockwell!")
        ratio = difflib.SequenceMatcher(None, q, c).ratio()
        assert ratio >= 0.82


class TestCensorForSearch:
    def test_censors_profanity(self):
        assert _censor_for_search("norman fucking rockwell") == "norman f*****g rockwell"

    def test_returns_unchanged_when_no_profanity(self):
        assert _censor_for_search("nevermind") == "nevermind"

    def test_case_insensitive_censoring(self):
        result = _censor_for_search("Norman Fucking Rockwell")
        assert result == "Norman F*****g Rockwell"


class TestSplitArtists:
    def test_splits_on_comma(self):
        assert _split_artists("Vijay Iyer, Wadada Leo Smith") == ["Vijay Iyer", "Wadada Leo Smith"]

    def test_splits_on_ampersand(self):
        assert _split_artists("billy woods & Kenny Segal") == ["billy woods", "Kenny Segal"]

    def test_splits_three_artists(self):
        assert _split_artists("Titanic, I la Católica, Mabe Fratti") == [
            "Titanic", "I la Católica", "Mabe Fratti"
        ]

    def test_single_artist_unchanged(self):
        assert _split_artists("Nirvana") == ["Nirvana"]

    def test_splits_on_feat(self):
        assert _split_artists("Artist feat. Other") == ["Artist", "Other"]


class TestArtistSimilarity:
    def test_identical_returns_1(self):
        assert _artist_similarity("Nirvana", "Nirvana") == 1.0

    def test_case_insensitive(self):
        assert _artist_similarity("FKA twigs", "FKA Twigs") == 1.0

    def test_first_of_multi_matches_single(self):
        # "Vijay Iyer, Wadada Leo Smith" — primary artist matches Apple's "Vijay Iyer"
        sim = _artist_similarity("Vijay Iyer, Wadada Leo Smith", "Vijay Iyer")
        assert sim == 1.0

    def test_comma_vs_ampersand_separator(self):
        # Our DB: comma-separated; Apple Music: ampersand-separated
        sim = _artist_similarity("billy woods, Kenny Segal", "billy woods & Kenny Segal")
        assert sim >= 0.90

    def test_completely_different_returns_low(self):
        sim = _artist_similarity("Nirvana", "Metallica")
        assert sim < 0.72

    def test_partial_name_match_does_not_reach_threshold(self):
        # "Pink" should not match "Pink Floyd" at artist threshold
        sim = _artist_similarity("Pink", "Pink Floyd")
        assert sim < 0.72


# ==================== FIND APPLE MUSIC ALBUM ====================


def _make_api_response(albums: list[dict], *, success: bool = True) -> MagicMock:
    resp = MagicMock()
    resp.is_success = success
    resp.status_code = 200 if success else 500
    resp.json.return_value = {"results": {"albums": {"data": albums}}}
    return resp


def _make_album_data(
    id: str = "123",
    name: str = "Test Album",
    artist: str = "Test Artist",
    release_date: str = "2020-01-01",
    genres: list[str] | None = None,
    artwork_url: str = "https://example.com/{w}x{h}.jpg",
) -> dict:
    return {
        "id": id,
        "attributes": {
            "name": name,
            "artistName": artist,
            "releaseDate": release_date,
            "genreNames": genres or [],
            "artwork": {"url": artwork_url},
        },
    }


class TestFindAppleMusicAlbum:
    def setup_method(self):
        am_client._dev_token = "test_token"
        am_client._dev_token_expires_at = 9_999_999_999.0

    def teardown_method(self):
        am_client._dev_token = None
        am_client._dev_token_expires_at = 0.0

    def test_returns_none_when_no_results(self):
        with patch("httpx.get", return_value=_make_api_response([])):
            result = find_apple_music_album("Unknown", "Unknown")
        assert result is None

    def test_returns_none_on_api_failure(self):
        with patch("httpx.get", return_value=_make_api_response([], success=False)):
            result = find_apple_music_album("Album", "Artist")
        assert result is None

    def test_returns_none_on_request_exception(self):
        with patch("httpx.get", side_effect=Exception("network error")):
            result = find_apple_music_album("Album", "Artist")
        assert result is None

    def test_returns_match_on_exact_title_and_artist(self):
        album = _make_album_data(id="999", name="My Album", artist="My Artist")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("My Album", "My Artist")
        assert result is not None
        assert result.id == "999"
        assert result.title == "My Album"
        assert result.artist == "My Artist"

    def test_interpolates_artwork_dimensions(self):
        album = _make_album_data(name="X", artist="Y", artwork_url="https://cdn.apple.com/{w}x{h}.jpg")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("X", "Y")
        assert result is not None
        assert result.cover_url == "https://cdn.apple.com/300x300.jpg"

    def test_returns_none_when_artist_completely_differs(self):
        album = _make_album_data(name="My Album", artist="Wrong Artist")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("My Album", "My Artist")
        assert result is None

    def test_matches_when_query_has_edition_suffix_candidate_does_not(self):
        # "Nevermind (Remastered)" in our DB should match Apple's clean "Nevermind"
        album = _make_album_data(name="Nevermind", artist="Nirvana")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("Nevermind (Remastered)", "Nirvana")
        assert result is not None
        assert result.title == "Nevermind"

    def test_matches_complex_expanded_remastered_parenthetical(self):
        album = _make_album_data(
            name="In the Court of the Crimson King",
            artist="King Crimson",
        )
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album(
                "In The Court Of The Crimson King (Expanded & Remastered Original Album Mix)",
                "King Crimson",
            )
        assert result is not None

    def test_matches_both_sides_have_deluxe_suffix(self):
        album = _make_album_data(name="My Album (Deluxe Edition)", artist="My Artist")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("My Album (Deluxe Edition)", "My Artist")
        assert result is not None

    def test_matches_first_of_multiple_comma_separated_artists(self):
        # Apple Music uses the primary artist; our DB has "Vijay Iyer, Wadada Leo Smith"
        album = _make_album_data(
            name="A Cosmic Rhythm With Each Stroke",
            artist="Vijay Iyer",
        )
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album(
                "A Cosmic Rhythm With Each Stroke",
                "Vijay Iyer, Wadada Leo Smith",
            )
        assert result is not None

    def test_matches_comma_vs_ampersand_artist_separator(self):
        # Our DB: "billy woods, Kenny Segal"; Apple Music: "billy woods & Kenny Segal"
        album = _make_album_data(name="Maps", artist="billy woods & Kenny Segal")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("Maps", "billy woods, Kenny Segal")
        assert result is not None

    def test_falls_back_to_title_only_search_when_stage1_finds_nothing(self):
        # Stage 1 (title + first artist) returns empty; stage 2 (title only) finds the album.
        matching_album = _make_album_data(name="Maps", artist="billy woods & Kenny Segal")
        with patch("httpx.get", side_effect=[
            _make_api_response([]),           # stage 1: no results
            _make_api_response([matching_album]),  # stage 2: found
        ]) as mock_get:
            result = find_apple_music_album("Maps", "billy woods, Kenny Segal")
        assert result is not None
        assert result.title == "Maps"
        assert mock_get.call_count == 2

    def test_does_not_fall_back_when_stage1_succeeds(self):
        album = _make_album_data(name="Nevermind", artist="Nirvana")
        with patch("httpx.get", return_value=_make_api_response([album])) as mock_get:
            result = find_apple_music_album("Nevermind", "Nirvana")
        assert result is not None
        assert mock_get.call_count == 1

    def test_includes_genres(self):
        album = _make_album_data(name="X", artist="Y", genres=["Rock", "Alternative"])
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("X", "Y")
        assert result is not None
        assert result.genres == ["Rock", "Alternative"]

    def test_returns_none_when_unconfigured(self):
        am_client._dev_token = None
        am_client._dev_token_expires_at = 0.0
        mock_settings = MagicMock()
        mock_settings.APPLE_MUSIC_TEAM_ID = ""
        mock_settings.APPLE_MUSIC_KEY_ID = ""
        mock_settings.APPLE_MUSIC_PRIVATE_KEY = ""
        with patch("app.utils.apple_music_client.get_settings", return_value=mock_settings):
            result = find_apple_music_album("Album", "Artist")
        assert result is None

    def test_selects_higher_scoring_candidate_when_multiple_returned(self):
        # Both candidates pass title+artist thresholds, but the exact match scores higher.
        # "Nevermind 2" has title_sim ≈ 0.90 vs "Nevermind" at 1.0, so the exact match wins.
        weak = _make_album_data(id="1", name="Nevermind 2", artist="Nirvana")
        strong = _make_album_data(id="2", name="Nevermind", artist="Nirvana")
        with patch("httpx.get", return_value=_make_api_response([weak, strong])):
            result = find_apple_music_album("Nevermind", "Nirvana")
        assert result is not None
        assert result.id == "2"

    def test_matches_when_candidate_has_dash_ep_suffix(self):
        # Apple Music titles like "M3LL155X - EP" should match our "M3LL155X"
        album = _make_album_data(name="M3LL155X - EP", artist="FKA twigs")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("M3LL155X", "FKA twigs")
        assert result is not None
        assert result.title == "M3LL155X - EP"

    def test_matches_when_candidate_has_censored_profanity(self):
        # Apple stores/returns "Norman F*****g Rockwell!" (censored); our DB has the full title.
        album = _make_album_data(name="Norman F*****g Rockwell!", artist="Lana Del Rey")
        with patch("httpx.get", return_value=_make_api_response([album])):
            result = find_apple_music_album("Norman Fucking Rockwell!", "Lana Del Rey")
        assert result is not None

    def test_uses_censored_search_term_as_stage3_for_profanity_titles(self):
        # If stage 1 & 2 fail (Apple filters the profanity in search queries),
        # stage 3 retries with the Apple-style censored title.
        album = _make_album_data(name="Norman F*****g Rockwell!", artist="Lana Del Rey")
        with patch("httpx.get", side_effect=[
            _make_api_response([]),   # stage 1: "norman f*****g rockwell lana del rey" — no results
            _make_api_response([]),   # stage 2: "norman f*****g rockwell" — no results
            _make_api_response([album]),  # stage 3: censored term — found
        ]) as mock_get:
            result = find_apple_music_album("Norman Fucking Rockwell!", "Lana Del Rey")
        assert result is not None
        assert mock_get.call_count == 3
