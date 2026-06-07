#!/usr/bin/env python3
"""Simulate realistic SpinShare user sessions and report cache / DB metrics.

Usage
-----
# 1. Establish baseline (cache disabled):
CACHE_ENABLED=false TRACK_DB_QUERIES=true python scripts/simulate_traffic.py \\
    --url http://localhost:8000 \\
    --email you@example.com --password yourpassword \\
    --group-id 5 --album-id 566 --runs 5

# 2. Measure with cache enabled (default):
TRACK_DB_QUERIES=true python scripts/simulate_traffic.py \\
    --url http://localhost:8000 \\
    --email you@example.com --password yourpassword \\
    --group-id 5 --album-id 566 --runs 5

# 3. Include the Review History tab (requires a group_album_id):
TRACK_DB_QUERIES=true python scripts/simulate_traffic.py \\
    --url http://localhost:8000 \\
    --email you@example.com --password yourpassword \\
    --group-id 5 --album-id 566 --group-album-id 83 --runs 5

# 4. Reset hit/miss counters between runs:
python scripts/simulate_traffic.py \\
    --url http://localhost:8000 \\
    --email you@example.com --password yourpassword \\
    --reset

Compare the DB query counts and hit rates between both runs to confirm the
cache is having the expected impact.

Notes
-----
- Requires the app to be running locally with TRACK_DB_QUERIES=true in .env.
- The --group-id and --album-id arguments should be real IDs from your dev DB.
- --group-album-id is the GroupAlbum.id (not the album's Spotify/internal id).
  Find it with: SELECT id FROM group_albums WHERE group_id=<id> LIMIT 5;
- Use --runs to simulate multiple user sessions (higher = more representative).
- After the first session the cache is warm; subsequent sessions mostly hit it.
- Per-request timing is used as a cache-hit proxy: responses faster than
  CACHE_HIT_THRESHOLD_MS on sessions 2+ are reported as likely cache hits.
"""

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import httpx

# Default threshold for per-request cache classification (overridden by --cache-threshold-ms).
# See _check_threshold_calibration() for the NullPool caveat.
_DEFAULT_CACHE_HIT_THRESHOLD_MS: float = 20.0

# Module-level effective threshold — set by main() after parsing --cache-threshold-ms.
CACHE_HIT_THRESHOLD_MS: float = _DEFAULT_CACHE_HIT_THRESHOLD_MS

# ── Simulated request sequence per session ──────────────────────────────────
# Mirrors the access patterns visible in the production access log:
#   group page load → album detail → explore → navigate back (cache hits)
ENDPOINTS_PER_SESSION = [
    # Group page load
    ("GET",  "/groups/{group_id}/albums/today"),
    ("GET",  "/groups/{group_id}/stats"),
    ("GET",  "/groups/{group_id}/members"),
    ("GET",  "/groups/{group_id}/nominations/count"),
    # Album detail view (mirrors production log pattern)
    ("GET",  "/albums/{album_id}"),
    ("GET",  "/albums/{album_id}/stats"),
    ("GET",  "/albums/{album_id}/reviews?group_id={group_id}"),
    # Explore / stats pages
    ("GET",  "/explore/albums"),
    ("GET",  "/explore/stats"),
    # Navigate back to group — these should be cache hits on runs > 1
    ("GET",  "/groups/{group_id}/albums/today"),
    ("GET",  "/groups/{group_id}/stats"),
    ("GET",  "/albums/{album_id}/stats"),
]

# ── Review History tab endpoints ─────────────────────────────────────────────
# These fire when a user opens the Review History tab on the group page.
# --group-album-id is required for the guess-stats endpoint; the others only
# need group_id / album_id and are always included when this mode is active.
REVIEW_HISTORY_ENDPOINTS = [
    # Tab load: catalog + per-user lists
    ("GET",  "/groups/{group_id}/albums"),
    ("GET",  "/groups/{group_id}/reviews/me"),
    ("GET",  "/groups/{group_id}/guesses/me"),
    # Expanded row: all reviews for a specific album (group-scoped)
    ("GET",  "/albums/{album_id}/reviews?group_id={group_id}"),
]

REVIEW_HISTORY_GUESS_STATS_ENDPOINT = (
    "GET", "/stats/groups/{group_id}/albums/{group_album_id}/guesses"
)


# ── Per-request bookkeeping ──────────────────────────────────────────────────

@dataclass
class Sample:
    session: int
    status: int
    elapsed_ms: float


@dataclass
class EndpointRecord:
    method: str
    label: str          # display path (IDs filled in)
    template: str       # original template (used for grouping)
    samples: list[Sample] = field(default_factory=list)

    def add(self, session: int, status: int, elapsed_ms: float) -> None:
        self.samples.append(Sample(session, status, elapsed_ms))

    # ── Derived metrics ──────────────────────────────────────────────────────

    @property
    def call_count(self) -> int:
        return len(self.samples)

    @property
    def errors(self) -> list[Sample]:
        return [s for s in self.samples if s.status >= 400]

    @property
    def warm_samples(self) -> list[Sample]:
        """Sessions 2+ only — the cache is warm by then."""
        return [s for s in self.samples if s.session > 1]

    def avg_ms(self, samples: list[Sample] | None = None) -> float:
        target = samples if samples is not None else self.samples
        return sum(s.elapsed_ms for s in target) / len(target) if target else 0.0

    def min_ms(self, samples: list[Sample] | None = None) -> float:
        target = samples if samples is not None else self.samples
        return min(s.elapsed_ms for s in target) if target else 0.0

    @property
    def likely_cached(self) -> bool | None:
        """None when there are no warm sessions to judge from.

        Uses the module-level CACHE_HIT_THRESHOLD_MS (set by --cache-threshold-ms).
        """
        warm = self.warm_samples
        if not warm:
            return None
        return self.avg_ms(warm) < CACHE_HIT_THRESHOLD_MS


def _print_request_table(records: list[EndpointRecord], runs: int) -> None:
    """Print a per-endpoint breakdown table."""
    # Column widths
    label_w = max(len(r.label) for r in records) + 2
    label_w = max(label_w, len("Endpoint") + 2)

    header = (
        f"  {'Endpoint':<{label_w}}  {'Calls':>5}  {'Errors':>6}  "
        f"{'Avg ms':>7}  {'Warm avg':>8}  {'Status'}"
    )
    separator = "  " + "-" * (len(header) - 2)
    print(separator)
    print(header)
    print(separator)

    for rec in records:
        warm = rec.warm_samples
        warm_avg = f"{rec.avg_ms(warm):>7.1f}" if warm else "    n/a"
        error_str = f"{len(rec.errors):>6}" if rec.errors else "     —"

        cached = rec.likely_cached
        if cached is None:
            status_icon = "  (only 1 session)"
        elif cached:
            status_icon = "  ✓ likely cached"
        else:
            status_icon = "  ✗ likely not cached"

        if rec.errors:
            codes = ", ".join(sorted({str(s.status) for s in rec.errors}))
            hint = ""
            if any(s.status == 404 for s in rec.errors) and "group_album_id" in rec.template:
                hint = " (verify --group-album-id belongs to --group-id)"
            status_icon += f"  ⚠ errors: {codes}{hint}"

        print(
            f"  {rec.label:<{label_w}}  {rec.call_count:>5}  {error_str}  "
            f"{rec.avg_ms():>7.1f}  {warm_avg}  {status_icon}"
        )

    print(separator)
    if runs > 1:
        print(
            f"  * 'Warm avg' = avg response time on sessions 2–{runs} "
            f"(threshold for cached: <{CACHE_HIT_THRESHOLD_MS:.0f}ms)"
        )
    print()


# ── Network helpers ──────────────────────────────────────────────────────────

def authenticate(base_url: str, email: str, password: str) -> str:
    """Return a fresh access token."""
    import re
    payload: dict = {"password": password}
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        payload["email"] = email
    else:
        payload["username"] = email
    resp = httpx.post(
        f"{base_url}/users/login",
        json=payload,
        follow_redirects=True,
    )
    if resp.status_code != 200:
        print(f"[ERROR] Login failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["access_token"]


def reset_metrics(base_url: str, headers: dict, *, fatal: bool = False) -> None:
    """Reset cache stats and DB query counter on the server."""
    def _check(resp: httpx.Response, label: str) -> None:
        if resp.status_code == 200:
            print(f"  ✓ {label}")
        else:
            msg = f"[{'ERROR' if fatal else 'WARN'}] {label} failed ({resp.status_code}): {resp.text}"
            print(msg, file=sys.stderr)
            if fatal:
                sys.exit(1)

    _check(httpx.post(f"{base_url}/admin/cache/reset-stats", headers=headers), "Hit/miss counters reset")
    _check(httpx.post(f"{base_url}/admin/cache/clear", headers=headers), "Cache entries cleared")


def fetch_metrics(base_url: str, headers: dict) -> dict:
    """Fetch cache stats from the admin endpoint."""
    resp = httpx.get(f"{base_url}/admin/cache/stats", headers=headers)
    if resp.status_code == 403:
        print(
            "[ERROR] /admin/cache/stats returned 403 — ensure the account has is_admin=True.",
            file=sys.stderr,
        )
        sys.exit(1)
    if resp.status_code != 200:
        print(f"[ERROR] Could not fetch stats ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def build_session_endpoints(group_album_id: int | None) -> list[tuple[str, str]]:
    """Return the full per-session endpoint list for this run."""
    endpoints = list(ENDPOINTS_PER_SESSION)
    if group_album_id is not None:
        endpoints += list(REVIEW_HISTORY_ENDPOINTS)
        endpoints.append(REVIEW_HISTORY_GUESS_STATS_ENDPOINT)
    return endpoints


# ── Simulation ───────────────────────────────────────────────────────────────

def run_simulation(
    base_url: str,
    headers: dict,
    group_id: int,
    album_id: int,
    runs: int,
    *,
    group_album_id: int | None = None,
    warm_cache: bool = False,
) -> None:
    """Execute `runs` simulated sessions and print a metrics report."""
    if not warm_cache:
        print("  → Resetting stats and clearing cache for a cold start …")
        reset_metrics(base_url, headers)
        print()

    session_endpoints = build_session_endpoints(group_album_id)
    fmt_kwargs = dict(group_id=group_id, album_id=album_id, group_album_id=group_album_id)

    # Build ordered record list (preserves endpoint order, deduplicates by template)
    records: list[EndpointRecord] = []
    record_index: dict[tuple[str, str], EndpointRecord] = {}
    for method, template in session_endpoints:
        key = (method, template)
        if key not in record_index:
            label = f"{method} {template.format(**fmt_kwargs)}"
            rec = EndpointRecord(method=method, label=label, template=template)
            records.append(rec)
            record_index[key] = rec

    with httpx.Client(base_url=base_url, headers=headers, follow_redirects=True) as client:
        for run_idx in range(1, runs + 1):
            print(f"  → Session {run_idx}/{runs} …", end="", flush=True)
            for method, template in session_endpoints:
                url = template.format(**fmt_kwargs)
                resp = client.request(method, url)
                elapsed_ms = resp.elapsed.total_seconds() * 1000
                record_index[(method, template)].add(run_idx, resp.status_code, elapsed_ms)
            print(" done")

    stats = fetch_metrics(base_url, headers)

    # ── Per-request breakdown ────────────────────────────────────────────────
    total_calls = sum(r.call_count for r in records)
    total_errors = sum(len(r.errors) for r in records)
    print(f"\n{'─' * 60}")
    print(f"  Request breakdown  ({runs} sessions × {len(session_endpoints)} endpoints = {total_calls} calls)")
    _print_request_table(records, runs)

    # ── Aggregate cache / DB summary ─────────────────────────────────────────
    review_history_note = (
        f"incl. {len(REVIEW_HISTORY_ENDPOINTS) + 1} review history endpoints"
        if group_album_id is not None
        else "add --group-album-id to include review history endpoints"
    )
    divider = "=" * 60
    print(divider)
    print(f"  Cache enabled:     {stats.get('cache_enabled', '?')}  ({review_history_note})")
    print(f"  Cache hits:        {stats['hits']}")
    print(f"  Cache misses:      {stats['misses']}")
    print(f"  Hit rate:          {stats['hit_rate'] * 100:.1f}%")
    print(f"  Invalidations:     {stats['invalidations']}")
    print(f"  Cache size:        {stats['current_size']} entries")
    if "db_queries" in stats:
        print(f"  DB queries:        {stats['db_queries']}")
        print(f"  DB queries saved:  ~{stats['hits']} (≈ hit count, estimated)")
    else:
        print("  DB queries:        (set TRACK_DB_QUERIES=true in .env to see this)")
    if total_errors:
        print(f"  Request errors:    {total_errors} (see breakdown above for details)")
    print(f"{divider}\n")

    # ── Interpretation guide ─────────────────────────────────────────────────
    hit_rate = stats["hit_rate"]
    if hit_rate >= 0.60:
        print(f"  ✅  Hit rate {hit_rate * 100:.0f}% — cache is working as expected.")
    elif hit_rate >= 0.30:
        print(
            f"  ⚠️  Hit rate {hit_rate * 100:.0f}% — lower than expected. "
            "Check that cached endpoints are being called in the session sequence."
        )
    else:
        print(
            f"  ❌  Hit rate {hit_rate * 100:.0f}% — very low. "
            "Verify CACHE_ENABLED=true and that the server was restarted after enabling caching."
        )

    uncached = [r for r in records if r.likely_cached is False]
    if uncached:
        print(
            f"\n  Endpoints with no cache coverage ({len(uncached)}):\n"
            + "\n".join(f"    • {r.label}" for r in uncached)
        )


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate SpinShare user sessions and report cache/DB metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the backend")
    parser.add_argument("--email", required=True, help="Admin account email or username")
    parser.add_argument("--password", required=True, help="Admin account password")
    parser.add_argument(
        "--group-id",
        type=int,
        default=None,
        help="Group ID to use in requests (required unless --reset is the only action)",
    )
    parser.add_argument(
        "--album-id",
        type=int,
        default=None,
        help="Album ID to use in requests (required unless --reset is the only action)",
    )
    parser.add_argument(
        "--group-album-id",
        type=int,
        default=None,
        help=(
            "GroupAlbum.id for the test album in the test group — enables Review History "
            "endpoints. Find it with: SELECT id FROM group_albums WHERE group_id=<id> LIMIT 5"
        ),
    )
    parser.add_argument("--runs", default=5, type=int, help="Number of simulated sessions (default: 5)")
    parser.add_argument(
        "--cache-threshold-ms",
        type=float,
        default=_DEFAULT_CACHE_HIT_THRESHOLD_MS,
        help=(
            f"Responses faster than this on warm sessions are classified as likely-cached "
            f"(default: {_DEFAULT_CACHE_HIT_THRESHOLD_MS:.0f}ms). "
            "Raise this if your local DB is fast and misclassifying misses as hits."
        ),
    )
    parser.add_argument(
        "--warm",
        action="store_true",
        help="Skip cache clear — use when cache is already warm from a prior run",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset hit/miss counters and clear all cache entries, then exit (no simulation run)",
    )
    args = parser.parse_args()

    # --group-id and --album-id are required for simulation runs but optional for --reset.
    if not args.reset and (args.group_id is None or args.album_id is None):
        parser.error("--group-id and --album-id are required unless --reset is used alone")

    # Apply the threshold override before any EndpointRecord.likely_cached calls.
    global CACHE_HIT_THRESHOLD_MS
    CACHE_HIT_THRESHOLD_MS = args.cache_threshold_ms

    review_history_str = str(args.group_album_id) if args.group_album_id else "not included (no --group-album-id)"
    print(f"\nSpinShare traffic simulation")
    print(f"  Target:         {args.url}")
    if not args.reset:
        print(f"  Group:          {args.group_id}  |  Album: {args.album_id}  |  Runs: {args.runs}")
        print(f"  Group-album-id: {review_history_str}")
        print(f"  Cache:          {'warm (skip clear)' if args.warm else 'cold start (clear first)'}")
    print()

    print("Authenticating …")
    token = authenticate(args.url, args.email, args.password)
    headers = {"Authorization": f"Bearer {token}"}
    print("  ✓ Login successful\n")

    if args.reset:
        print("Resetting cache stats …")
        reset_metrics(args.url, headers, fatal=True)
        print("\nDone.")
        return

    run_simulation(
        args.url,
        headers,
        group_id=args.group_id,
        album_id=args.album_id,
        runs=args.runs,
        group_album_id=args.group_album_id,
        warm_cache=args.warm,
    )


if __name__ == "__main__":
    main()
