"""Resolve the Wikipedia URL for an album/artist against the live MediaWiki API.

A manual pre-deployment check for the self-healing Wikipedia link feature — it calls the
pure client directly, so no database or running server is required.

Run from the backend/ directory:
    .venv/bin/python scripts/wikipedia_lookup.py "In Rainbows" "Radiohead"
    .venv/bin/python scripts/wikipedia_lookup.py "In Rainbows" "Radiohead" -v
"""

import argparse
import difflib
import sys

sys.path.insert(0, ".")

from app.utils import wikipedia_client  # noqa: E402


def _print_candidates(label: str, srsearch: str, expected: str) -> None:
    """Print each search candidate with its similarity score against ``expected``."""
    normalized_expected = wikipedia_client._normalize_page_title(expected)
    print(f"\n{label} (srsearch={srsearch!r}):")
    titles = wikipedia_client._search_titles(srsearch)
    if not titles:
        print("  (no results)")
        return
    for title in titles:
        score = difflib.SequenceMatcher(
            None, normalized_expected, wikipedia_client._normalize_page_title(title)
        ).ratio()
        print(f"  {score:.3f}  {title}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve the Wikipedia URL for an album")
    parser.add_argument("title", help="Album title")
    parser.add_argument("artist", help="Artist name")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show raw album/artist search candidates and their similarity scores",
    )
    args = parser.parse_args()

    if args.verbose:
        _print_candidates(
            "Album search", f"{args.title} {args.artist} album", args.title,
        )
        _print_candidates("Artist search", args.artist, args.artist)
        print(
            f"\nThresholds: title>={wikipedia_client._TITLE_THRESHOLD} "
            f"artist>={wikipedia_client._ARTIST_THRESHOLD}"
        )

    url = wikipedia_client.find_wikipedia_url(args.title, args.artist)
    print()
    if url:
        print(f"Resolved: {url}")
    else:
        print(f"No Wikipedia page found for {args.title!r} by {args.artist!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
