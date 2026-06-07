"""In-process TTL cache for reducing repeated database hits.

Single-process deployment (one Uvicorn worker) — module-level singleton is shared
across all request handlers. Thread-safe via threading.Lock.

Usage::

    from app.utils.cache import cache, SITE_STATS_TTL, _key

    def get_site_stats(self) -> SiteStatsResponse:
        ck = _key("explore", "site_stats")
        cached = cache.get(ck)
        if cached is not None:
            return cached
        result = ...  # expensive DB query
        cache.set(ck, result, SITE_STATS_TTL)
        return result

Invalidation::

    cache.delete(_key("explore", "site_stats"))
    cache.delete_prefix("groups:42:")   # evict all keys for group 42

Migration to Redis::

    When scaling to multiple workers, implement RedisTTLCache with the same
    interface (get/set/delete/delete_prefix/clear/stats/reset_stats) and swap
    the singleton below based on settings.CACHE_BACKEND.
"""

import time
import threading
from typing import Any

from app.config import get_settings

_settings = get_settings()

# Sentinel used to distinguish "not provided" from None in get() default
_SENTINEL = object()


class TTLCache:
    """Thread-safe in-process key/value cache with per-entry TTL and hit/miss metrics.

    Values are stored as (payload, expiry_monotonic) pairs. Expiry is checked lazily
    on get — no background eviction thread is needed at this traffic scale.

    All mutations (set, delete, clear) and counter increments happen inside a
    threading.Lock so the cache is safe for concurrent requests on a single worker.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    # ── Read ──────────────────────────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        """Return the cached value for *key*, or None if missing / expired.

        Also returns None when CACHE_ENABLED=false (bypass mode for benchmarking).
        """
        if not _settings.CACHE_ENABLED:
            with self._lock:
                self._misses += 1
            return None

        with self._lock:
            entry = self._store.get(key)

        if entry is None:
            with self._lock:
                self._misses += 1
            return None

        value, expiry = entry
        if time.monotonic() > expiry:
            with self._lock:
                self._store.pop(key, None)
                self._misses += 1
            return None

        with self._lock:
            self._hits += 1
        return value

    # ── Write ─────────────────────────────────────────────────────────────────

    def set(self, key: str, value: Any, ttl: float) -> None:
        """Store *value* under *key* with an expiry of *ttl* seconds from now.

        No-op when CACHE_ENABLED=false.
        """
        if not _settings.CACHE_ENABLED:
            return
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        """Evict a single key. Increments invalidation counter if key existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                self._invalidations += 1

    def delete_prefix(self, prefix: str) -> None:
        """Evict all keys whose names start with *prefix*.

        Useful for bulk-evicting all keys for a resource (e.g. ``groups:42:``).
        """
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
                self._invalidations += 1

    def clear(self) -> None:
        """Remove all entries. Does not affect metric counters."""
        with self._lock:
            self._store.clear()

    # ── Metrics ───────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return a snapshot of cache metrics and current state."""
        with self._lock:
            hits = self._hits
            misses = self._misses
            invalidations = self._invalidations
            size = len(self._store)

        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "invalidations": invalidations,
            "hit_rate": round(hits / total, 3) if total else 0.0,
            "total_lookups": total,
            "current_size": size,
            "cache_enabled": _settings.CACHE_ENABLED,
        }

    def reset_stats(self) -> None:
        """Reset hit/miss/invalidation counters to zero (does not clear entries)."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._invalidations = 0


# ── Module-level singleton ─────────────────────────────────────────────────────
# All service modules import this directly:  from app.utils.cache import cache
cache = TTLCache()

# ── TTL constants (seconds) ───────────────────────────────────────────────────
SITE_STATS_TTL     = 60 * 60        # 1 hr   — changes only on review/nomination
TODAYS_ALBUMS_TTL  = 6 * 60 * 60   # 6 hr   — static until daily selection draw
EXPLORE_ALBUMS_TTL = 5 * 60        # 5 min  — Bayesian pages, high scroll traffic
GROUP_STATS_TTL    = 3 * 60 * 60   # 3 hr   — aggregations, busted on daily draw
ALBUM_STATS_TTL    = 30 * 60       # 30 min — histogram, busted on review events
USER_PROFILE_TTL   = 30 * 60       # 30 min — busted on profile update
MEMBERSHIP_TTL     = 5 * 60        # 5 min  — acceptable gap for edge case (group kick)
REVIEW_HISTORY_TTL   = 60 * 60       # 1 hr   — review history page: catalog, group reviews, guess stats
GROUP_MEMBERS_TTL    = 10 * 60       # 10 min — members list; busted on add/remove/role-change
NOMINATION_COUNT_TTL = 5 * 60        # 5 min  — pending nomination count; busted on nominate/remove/daily-draw
AUTH_USER_TTL        = 15 * 60       # 15 min — matches access-token lifetime; busted on admin change/delete/update


def _key(*parts) -> str:
    """Build a colon-delimited cache key from *parts*.

    Example::

        _key("groups", 42, "stats")  →  "groups:42:stats"
    """
    return ":".join(str(p) for p in parts)
