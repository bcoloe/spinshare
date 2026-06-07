"""Admin-only endpoints for cache management and metrics.

All routes require admin privileges (current_user.is_admin=True).

Routes
------
GET  /api/admin/cache/stats        Return cache hit/miss metrics and DB query count.
POST /api/admin/cache/reset-stats  Reset hit/miss/invalidation counters to zero.
POST /api/admin/cache/clear        Flush all cache entries (forces a cold-start).
"""

from fastapi import APIRouter, Depends

from app.database import get_db_query_count, reset_db_query_count
from app.dependencies import get_current_admin_user
from app.models import User
from app.utils.cache import cache

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cache/stats")
def get_cache_stats(current_user: User = Depends(get_current_admin_user)) -> dict:
    """Return a snapshot of in-process cache metrics and (if enabled) DB query count.

    Useful for confirming cache warm-up post-deploy and for before/after benchmarking
    with the simulate_traffic.py script.

    Response fields
    ---------------
    hits            — number of cache lookups that returned a valid entry
    misses          — number of cache lookups that returned None (cold or expired)
    invalidations   — number of explicit delete/delete_prefix calls
    hit_rate        — hits / (hits + misses), 0.0 when no lookups yet
    total_lookups   — hits + misses
    current_size    — number of entries currently in the cache
    cache_enabled   — mirrors settings.CACHE_ENABLED
    db_queries      — raw DB cursor executions since last reset (requires TRACK_DB_QUERIES=true)
    """
    stats = cache.stats()
    db_count = get_db_query_count()
    if db_count > 0:
        stats["db_queries"] = db_count
    return stats


@router.post("/cache/reset-stats")
def reset_cache_stats(current_user: User = Depends(get_current_admin_user)) -> dict:
    """Reset hit/miss/invalidation counters and DB query count to zero.

    Cache entries are NOT removed — only the metric counters are cleared.
    Useful before starting a benchmark run so measurements reflect only the
    traffic you're about to generate.
    """
    cache.reset_stats()
    reset_db_query_count()
    return {"message": "Cache stats and DB query count reset"}


@router.post("/cache/clear")
def clear_cache(current_user: User = Depends(get_current_admin_user)) -> dict:
    """Flush all entries from the in-process cache.

    Forces a cold-start on the next request to each cached endpoint. Metric
    counters are NOT reset — use /reset-stats separately if needed.

    Primarily useful during local benchmarking to compare cold vs warm behaviour.
    """
    cache.clear()
    return {"message": "Cache cleared"}
