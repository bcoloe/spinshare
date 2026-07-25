"""Scheduling helpers for the self-healing Wikipedia link backfill.

Shared by the album and group-album routers so every entry point that surfaces an album
(nomination, URL resolve, detail view, daily draw) can lazily heal its Wikipedia link with a
single call. The actual lookup runs in a FastAPI background task against its own DB session.
"""

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from fastapi import BackgroundTasks

# How long a resolved (or absent) Wikipedia link is trusted before a read re-triggers lookup.
WIKIPEDIA_TTL = timedelta(days=30)


def _run_backfill(album_id: int, title: str, artist: str) -> None:
    """Background task that resolves an album's Wikipedia URL in its own DB session."""
    from app.services.album_service import AlbumService

    db = SessionLocal()
    try:
        AlbumService(db).backfill_wikipedia_url(album_id, title, artist)
    finally:
        db.close()


def needs_check(album) -> bool:
    """Whether an album should have its Wikipedia URL (re)resolved.

    Only rows without a URL are healed; a stored value (auto-resolved or an admin override)
    is left untouched. Absent-URL rows are re-checked once their last check ages past the TTL.
    """
    if album.wikipedia_url is not None:
        return False
    if album.wikipedia_checked_at is None:
        return True
    return datetime.now(timezone.utc) - album.wikipedia_checked_at > WIKIPEDIA_TTL


def schedule(background_tasks: BackgroundTasks, album) -> None:
    """Schedule a background Wikipedia lookup for ``album`` if it needs one."""
    if needs_check(album):
        background_tasks.add_task(_run_backfill, album.id, album.title, album.artist)


def schedule_many(background_tasks: BackgroundTasks, albums) -> None:
    """Schedule background Wikipedia lookups for any albums in ``albums`` that need one."""
    for album in albums:
        schedule(background_tasks, album)
