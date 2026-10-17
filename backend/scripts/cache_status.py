"""Show, or clear, the API's in-process response cache. Run it on the API host.

It mints a one-minute admin access token with the server's own SECRET_KEY, so no
password is involved, and calls the API over localhost. The admin check behind
the endpoint loads that user, so the id must belong to a site admin.

Usage (from backend/):
    .venv/bin/python scripts/cache_status.py --admin-id 1           # summary
    .venv/bin/python scripts/cache_status.py --admin-id 1 --json    # raw counters
    .venv/bin/python scripts/cache_status.py --admin-id 1 --clear   # after an out-of-process write

SPINSHARE_ADMIN_ID in the environment can stand in for --admin-id.

Counters reset whenever the API restarts (every deploy), so judge the hit rate
after it has been up a day or two. What matters in the end is Neon's compute-hours;
see backend/CLAUDE.md, "Response Cache".
"""

import argparse
import json
import os
import sys
from datetime import timedelta

import httpx

# Ensure the app package is importable when run from the backend/ directory.
sys.path.insert(0, ".")

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def mint_token(admin_id: int) -> str:
    from app.utils.security import create_access_token

    return create_access_token({"sub": str(admin_id)}, expires_delta=timedelta(minutes=1))


def fetch(client: httpx.Client, token: str, *, clear: bool = False) -> dict:
    """GET the cache status, or POST a clear (which also returns the status)."""
    headers = {"Authorization": f"Bearer {token}"}
    if clear:
        resp = client.post("/admin/cache/clear", headers=headers)
    else:
        resp = client.get("/admin/cache", headers=headers)
    if resp.status_code == 401:
        raise SystemExit("401: the token was refused. Is this the same SECRET_KEY the API runs with?")
    if resp.status_code == 403:
        raise SystemExit("403: that user is not a site admin. Pass an admin's id with --admin-id.")
    resp.raise_for_status()
    return resp.json()


def summarize(status: dict) -> str:
    lookups = status["hits"] + status["misses"]
    rate = f"{status['hits'] / lookups:.1%}" if lookups else "n/a (no lookups yet)"
    mb = 1024 * 1024
    return "\n".join([
        f"enabled      {status['enabled']}",
        f"hit rate     {rate}   ({status['hits']} hits / {lookups} lookups)",
        f"invalidated  {status['stale']}   (found, but out of date: a write or expiry)",
        f"bypassed     {status['bypassed']}   (tokens that didn't verify)",
        f"entries      {status['entries']}   ({status['bytes'] / mb:.1f} of {status['max_bytes'] / mb:.0f} MB)",
        "(counters reset when the API restarts)",
    ])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Show or clear the API's response cache")
    parser.add_argument("--admin-id", type=int, default=os.environ.get("SPINSHARE_ADMIN_ID"),
                        help="Id of a site admin to act as (or set SPINSHARE_ADMIN_ID)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Where the API listens")
    parser.add_argument("--clear", action="store_true", help="Empty the cache, then show it")
    parser.add_argument("--json", action="store_true", help="Print the raw counters")
    args = parser.parse_args(argv)
    if args.admin_id is None:
        parser.error("--admin-id (or SPINSHARE_ADMIN_ID) is required")

    try:
        with httpx.Client(base_url=args.base_url, timeout=10) as client:
            status = fetch(client, mint_token(int(args.admin_id)), clear=args.clear)
    except httpx.ConnectError:
        raise SystemExit(f"Could not reach the API at {args.base_url}. Is spinshare-api running?") from None

    if args.clear:
        print("cache cleared")
    print(json.dumps(status, indent=2) if args.json else summarize(status))


if __name__ == "__main__":
    main()
