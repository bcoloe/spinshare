"""Resolve the Wikipedia URL for an album/artist against the live MediaWiki API.

A manual check for the self-healing Wikipedia link feature — it calls the pure client
directly, so no database or running server is required.

Run from the backend/ directory:
    .venv/bin/python scripts/wikipedia_lookup.py "In Rainbows" "Radiohead"
    .venv/bin/python scripts/wikipedia_lookup.py "In Rainbows" "Radiohead" -v
"""

import argparse
import sys

sys.path.insert(0, ".")

from app.utils import wikipedia_client as wc  # noqa: E402


def _print_album_candidates(label: str, pages: list, title: str, artist: str) -> None:
    """Print each album candidate with its classification and title score."""
    print(f"\n{label}:")
    if not pages:
        print("  (no pages)")
    for p in pages:
        print(
            f"  {wc._album_score(p, title):.3f}  album={wc._is_album_page(p)!s:5} "
            f"credits={wc._credits_artist(p, artist)!s:5}  {p.title}  — {p.shortdesc!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve the Wikipedia URL for an album")
    parser.add_argument("title", help="Album title")
    parser.add_argument("artist", help="Artist name")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show album candidates with their classification and similarity scores",
    )
    args = parser.parse_args()

    if args.verbose:
        clean = wc._clean_album_title(args.title)
        print(f"Cleaned title: {clean!r}   artist names: {wc._artist_names(args.artist)}")
        guesses = [clean, f"{clean} (album)", f"{clean} ({args.artist} album)"]
        _print_album_candidates(
            "Title guesses", wc._lookup_titles(guesses), args.title, args.artist
        )
        _print_album_candidates(
            "Search", wc._search(f"{clean} {args.artist} album"), args.title, args.artist
        )
        print(f"\nThresholds: title>={wc._TITLE_THRESHOLD} artist>={wc._ARTIST_THRESHOLD}")

    url = wc.find_wikipedia_url(args.title, args.artist)
    print()
    if url:
        print(f"Resolved: {url}")
    else:
        print(f"No Wikipedia page found for {args.title!r} by {args.artist!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
