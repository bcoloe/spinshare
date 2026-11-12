"""Tests for the Wikipedia client utility."""

from unittest.mock import MagicMock, patch

import pytest
from app.utils.wikipedia_client import (
    _clean_album_title,
    _normalize_page_title,
    _normalize_text,
    _page_url,
    find_wikipedia_url,
)

# ==================== FAKE MEDIAWIKI ====================


def _page(shortdesc: str = "", categories: tuple[str, ...] = (), disambiguation: bool = False):
    props = {}
    if shortdesc:
        props["wikibase-shortdesc"] = shortdesc
    if disambiguation:
        props["disambiguation"] = ""
    return {"pageprops": props, "categories": [{"title": f"Category:{c}"} for c in categories]}


class FakeWiki:
    """Answers ``httpx.get`` like the MediaWiki query API for a fixed set of pages.

    ``pages`` maps exact titles to page metadata; ``search`` maps a search query to the
    ranked titles it returns (unknown queries return nothing).
    """

    def __init__(self, pages: dict, search: dict | None = None, fail: bool = False):
        self.pages = pages
        self.search = search or {}
        self.fail = fail
        self.calls: list[dict] = []

    def _render(self, title: str, index: int | None = None) -> dict:
        if title not in self.pages:
            return {"title": title, "missing": True}
        page = {"title": title, **self.pages[title]}
        if index is not None:
            page["index"] = index
        return page

    def __call__(self, url, params, headers, timeout):
        self.calls.append(params)
        resp = MagicMock()
        resp.is_success = not self.fail
        resp.status_code = 429 if self.fail else 200
        if "titles" in params:
            rendered = [self._render(t) for t in params["titles"].split("|")]
        else:
            hits = self.search.get(params["gsrsearch"], [])
            rendered = [self._render(t, i + 1) for i, t in enumerate(hits)]
        resp.json.return_value = {"query": {"pages": rendered}}
        return resp


def _resolve(wiki: FakeWiki, title: str, artist: str) -> str | None:
    with patch("httpx.get", side_effect=wiki):
        return find_wikipedia_url(title, artist)


RADIOHEAD = _page("English rock band", ("English rock music groups",))
BROKEN_BELLS_BAND = _page("American rock band", ("Musical groups established in 2009",))
BROKEN_BELLS_ALBUM = _page(
    "2010 studio album by Broken Bells", ("2010 debut albums", "Broken Bells albums")
)


# ==================== NORMALIZATION / URL HELPERS ====================


class TestNormalizePageTitle:
    def test_strips_disambiguation_parenthetical(self):
        assert _normalize_page_title("Thriller (album)") == "thriller"

    def test_strips_artist_qualified_parenthetical(self):
        assert _normalize_page_title("1989 (Taylor Swift album)") == "1989"

    def test_strips_diacritics_and_punctuation(self):
        assert _normalize_page_title("Björk!") == "bjork"


class TestNormalizeText:
    def test_ampersand_is_spelled_out(self):
        assert _normalize_text("Nick Cave & The Bad Seeds") == "nick cave and the bad seeds"


class TestCleanAlbumTitle:
    @pytest.mark.parametrize(
        "raw, clean",
        [
            ("Abbey Road (Remastered 2019)", "Abbey Road"),
            ("Rumours [Super Deluxe]", "Rumours"),
            ("Pinkerton - Deluxe Edition", "Pinkerton"),
            ("ATLiens (25th Anniversary Deluxe Edition)", "ATLiens"),
            ("The Inner Mounting Flame (with John McLaughlin)", "The Inner Mounting Flame"),
            (
                "How To Train Your Dragon (Music From The Motion Picture)",
                "How To Train Your Dragon",
            ),
            # Not release noise — left alone.
            ("Red (Taylor's Version)", "Red (Taylor's Version)"),
            ("Weezer (Blue Album)", "Weezer (Blue Album)"),
        ],
    )
    def test_strips_only_release_variant_suffixes(self, raw, clean):
        assert _clean_album_title(raw) == clean


class TestPageUrl:
    def test_spaces_become_underscores(self):
        assert _page_url("In Rainbows") == "https://en.wikipedia.org/wiki/In_Rainbows"

    def test_parentheses_are_percent_encoded(self):
        assert _page_url("1989 (album)") == "https://en.wikipedia.org/wiki/1989_%28album%29"


# ==================== FIND WIKIPEDIA URL ====================


class TestFindAlbumPage:
    def test_returns_album_page_from_exact_title(self):
        wiki = FakeWiki({"In Rainbows": _page("2007 studio album by Radiohead")})
        assert _resolve(wiki, "In Rainbows", "Radiohead") == (
            "https://en.wikipedia.org/wiki/In_Rainbows"
        )
        # A verified title guess short-circuits before any search.
        assert len(wiki.calls) == 1

    def test_self_titled_album_beats_band_page(self):
        """Regression for #185: the band page shares the album's title."""
        wiki = FakeWiki(
            {"Broken Bells": BROKEN_BELLS_BAND, "Broken Bells (album)": BROKEN_BELLS_ALBUM}
        )
        assert _resolve(wiki, "Broken Bells", "Broken Bells") == (
            "https://en.wikipedia.org/wiki/Broken_Bells_%28album%29"
        )

    def test_self_titled_album_found_via_search(self):
        wiki = FakeWiki(
            {"Broken Bells": BROKEN_BELLS_BAND, "Broken Bells (2010)": BROKEN_BELLS_ALBUM},
            search={"Broken Bells Broken Bells album": ["Broken Bells", "Broken Bells (2010)"]},
        )
        assert _resolve(wiki, "Broken Bells", "Broken Bells").endswith("Broken_Bells_%282010%29")

    def test_rejects_same_titled_album_by_another_artist(self):
        wiki = FakeWiki(
            {
                "Blue (album)": _page("1996 studio album by LeAnn Rimes"),
                "Blue (Weezer album)": _page("album by Weezer"),
            }
        )
        assert _resolve(wiki, "Blue", "Joni Mitchell") is None

    def test_rejects_song_page(self):
        wiki = FakeWiki(
            {
                "Creep": _page("1992 single by Radiohead", ("Radiohead songs",)),
                "Radiohead": RADIOHEAD,
            }
        )
        assert _resolve(wiki, "Creep", "Radiohead") == "https://en.wikipedia.org/wiki/Radiohead"

    def test_rejects_disambiguation_page(self):
        wiki = FakeWiki({"Thriller": _page("", ("Radiohead albums",), disambiguation=True)})
        assert _resolve(wiki, "Thriller", "Radiohead") is None

    def test_artist_confirmed_by_category_without_short_description(self):
        wiki = FakeWiki({"Kid A": _page("", ("2000 albums", "Radiohead albums"))})
        assert _resolve(wiki, "Kid A", "Radiohead").endswith("/Kid_A")

    def test_artist_confirmed_by_title_qualifier(self):
        wiki = FakeWiki({"Blue (Joni Mitchell album)": _page("", ("1971 albums",))})
        assert _resolve(wiki, "Blue", "Joni Mitchell").endswith("Blue_%28Joni_Mitchell_album%29")

    def test_artist_match_tolerates_ampersand_and_stylization(self):
        wiki = FakeWiki(
            {
                "Ghosteen": _page("2019 studio album by Nick Cave and the Bad Seeds"),
                "Testing (album)": _page("2018 studio album by American rapper ASAP Rocky"),
            },
            # Titles are case-sensitive, so the all-caps guesses miss; search finds it.
            search={"TESTING A$AP Rocky album": ["Testing (album)"]},
        )
        assert _resolve(wiki, "Ghosteen", "Nick Cave & The Bad Seeds").endswith("/Ghosteen")
        assert _resolve(wiki, "TESTING", "A$AP Rocky").endswith("/Testing_%28album%29")

    def test_collaboration_credits_any_listed_artist(self):
        wiki = FakeWiki({"Watch the Throne": _page("2011 album by Jay-Z and Kanye West")})
        assert _resolve(wiki, "Watch the Throne", "JAY-Z, Kanye West").endswith("/Watch_the_Throne")

    def test_release_variant_suffix_is_ignored(self):
        wiki = FakeWiki({"Nevermind": _page("1991 studio album by Nirvana")})
        assert _resolve(wiki, "Nevermind (Remastered)", "Nirvana").endswith("/Nevermind")

    def test_distinct_release_article_beats_original(self):
        wiki = FakeWiki(
            {
                "Red (Taylor's Version)": _page("2021 re-recorded album by Taylor Swift"),
                "Red (Taylor Swift album)": _page("2012 studio album by Taylor Swift"),
            }
        )
        assert _resolve(wiki, "Red (Taylor's Version)", "Taylor Swift").endswith(
            "Red_%28Taylor%27s_Version%29"
        )

    def test_streaming_only_subtitle_is_ignored(self):
        wiki = FakeWiki(
            {"Praise a Lord": _page("2023 studio album by Yves Tumor")},
            search={"Praise a Lord (Or Simply, Hot) Yves Tumor album": ["Praise a Lord"]},
        )
        assert _resolve(wiki, "Praise a Lord (Or Simply, Hot)", "Yves Tumor").endswith(
            "/Praise_a_Lord"
        )


class TestFindArtistPage:
    def test_falls_back_to_artist_page(self):
        wiki = FakeWiki({"Radiohead": RADIOHEAD})
        assert _resolve(wiki, "Obscure Bootleg", "Radiohead") == (
            "https://en.wikipedia.org/wiki/Radiohead"
        )

    def test_artist_fallback_skips_album_with_band_name(self):
        wiki = FakeWiki(
            {
                "Sublime": _page("1996 studio album by Sublime"),
                "Sublime (band)": _page("American ska punk band"),
            }
        )
        assert _resolve(wiki, "Robbin' the Hood", "Sublime").endswith("/Sublime_%28band%29")

    def test_artist_fallback_skips_non_music_page(self):
        wiki = FakeWiki(
            {"Drake": _page("", disambiguation=True), "Drake (musician)": _page("Canadian rapper")}
        )
        assert _resolve(wiki, "Unreleased Mixtape", "Drake").endswith("/Drake_%28musician%29")

    def test_artist_fallback_rejects_near_miss_name(self):
        wiki = FakeWiki({}, search={"MAVI musician band": ["Mavis (band)"]})
        wiki.pages["Mavis (band)"] = _page("Australian rock band")
        assert _resolve(wiki, "Some Album", "MAVI") is None

    def test_artist_fallback_tries_title_case(self):
        wiki = FakeWiki({"Mavi (rapper)": _page("American rapper")})
        assert _resolve(wiki, "Some Album", "MAVI").endswith("/Mavi_%28rapper%29")

    def test_returns_none_when_nothing_verifies(self):
        wiki = FakeWiki({"Radiohead": _page("Radio station in Ohio")})
        assert _resolve(wiki, "Obscure Bootleg", "Radiohead") is None


class TestFailureHandling:
    def test_returns_none_on_http_error(self):
        assert _resolve(FakeWiki({}, fail=True), "Anything", "Anyone") is None

    def test_failed_album_lookup_does_not_fall_back_to_artist(self):
        """A rate-limited album query must not be mistaken for "no album page"."""
        wiki = FakeWiki({"Radiohead": RADIOHEAD}, fail=True)
        assert _resolve(wiki, "In Rainbows", "Radiohead") is None
        assert len(wiki.calls) == 1

    def test_returns_none_and_never_raises_on_network_error(self):
        with patch("httpx.get", side_effect=Exception("network down")):
            # Must not propagate — safe as a background task.
            assert find_wikipedia_url("Anything", "Anyone") is None

    def test_skips_titles_with_invalid_characters(self):
        wiki = FakeWiki({})
        _resolve(wiki, "A|B", "Anyone")
        assert all("A|B" not in c.get("titles", "") for c in wiki.calls)
