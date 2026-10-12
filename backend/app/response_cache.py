"""In-process cache for read-heavy GET responses, invalidated by observed table writes.

Neon bills the minutes its compute is awake, and any query wakes it. This cache lets
a returning visitor's page load — and the token refresh that starts their session —
be answered from memory, so a session that changes nothing never touches the
database.

How it stays correct without per-endpoint bookkeeping:

* **Reads are observed, not declared.** While a cacheable response is computed, every
  SQL statement is inspected and the tables it names are recorded. The entry is
  stored with the version of each of those tables as of *before* the computation.
* **Writes are observed too.** Every INSERT/UPDATE/DELETE executed in this process,
  through any Session or engine, marks its target table. When the transaction
  commits, those tables' versions are bumped. An entry is served only while every
  table it read is still at the version it was computed from.
* **Time is a dependency.** Some answers change with no write at all ("today's"
  albums at midnight). Every entry expires at the next local midnight of any
  timezone a group uses — every "today" in the app is a group's local day. Code
  whose answer turns over at some
  other instant says so while computing it, with ``valid_until`` (pending
  invitations do this with their earliest ``expires_at``).
* **Entries are per viewer.** The key includes the caller's user id, so one person's
  view of a page — membership checks, hidden reviews — is never served to another.

Because versions are captured before the computation and bumped after the writer
commits, a reader racing a writer can only ever produce an entry that is already
invalid, never a stale one that looks valid.

What it cannot see: writes from another process (a CLI script, psql). After one of
those, clear the cache (``POST /admin/cache/clear``) or restart the API. The app
runs as a single worker, so there is exactly one cache to keep coherent.
"""

import contextvars
import functools
import logging
import re
import threading
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from cachetools import LRUCache
from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.utils.security import decode_access_token
from app.utils.time_helpers import DEFAULT_TZ

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


# ==================== POLICY ====================

# The GET routes served from the cache, by route template. A route belongs here only
# if its response is a function of the database, the caller, the request and the
# clock — nothing external such as a third-party API — and any dependence on the
# clock finer than the calendar day is declared with ``valid_until``. Every route
# listed must also be profiled in scripts/profile_db.py (enforced by
# scripts/profile_db_test.py).
CACHED_GETS: frozenset[str] = frozenset({
    # The shell every page fires.
    "/notifications",
    "/invitations/pending",
    "/users/me/stats",
    "/groups/search",
    # Group page.
    "/groups/{group_id}",
    "/groups/{group_id}/members",
    "/groups/{group_id}/nominations/count",
    "/groups/{group_id}/albums/today",
    # Review history tab.
    "/groups/{group_id}/albums/history",
    "/groups/{group_id}/reviews/me",
    "/groups/{group_id}/guesses/me",
    # Album page.
    "/albums/{album_id}",
    "/albums/{album_id}/stats",
    "/albums/{album_id}/reviews",
    "/albums/{album_id}/reviews/me",
    # Nominations tab.
    "/users/me/nominations",
})


# ==================== TABLE VERSIONS ====================


class TableVersions:
    """A counter per table, bumped each time a write to it commits."""

    def __init__(self):
        self._lock = threading.Lock()
        self._versions: dict[str, int] = {}

    def bump(self, tables: Iterable[str]) -> None:
        with self._lock:
            for table in tables:
                self._versions[table] = self._versions.get(table, 0) + 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._versions)

    def current(self, deps: dict[str, int]) -> bool:
        with self._lock:
            return all(self._versions.get(t, 0) == v for t, v in deps.items())


versions = TableVersions()

# The cacheable computation in progress on this request, if any. A context variable
# so it follows the request into the threadpool that runs sync endpoints and
# dependencies (the object itself is shared, so what they record is seen).
_current: contextvars.ContextVar["_Observation | None"] = contextvars.ContextVar(
    "response_cache_observation", default=None
)

_PENDING_WRITES = "response_cache_pending_writes"
_WRITE_TARGET = re.compile(r'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"?(\w+)"?', re.IGNORECASE)


@functools.cache
def _known_tables() -> frozenset[str]:
    from app.database import Base

    return frozenset(Base.metadata.tables)


@functools.cache
def _table_pattern() -> re.Pattern:
    names = sorted(_known_tables(), key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(map(re.escape, names)) + r")\b")


@functools.lru_cache(maxsize=4096)
def classify(statement: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return (tables named anywhere, tables written to) for a SQL statement.

    "Named anywhere" over-approximates what is read — a column that shares a table's
    name counts — which only ever costs a cache miss, never a stale hit.
    """
    known = _known_tables()
    named = frozenset(_table_pattern().findall(statement))
    written = frozenset(t for t in _WRITE_TARGET.findall(statement) if t in known)
    return named, written


@event.listens_for(Engine, "before_cursor_execute")
def _observe_statement(conn, cursor, statement, parameters, context, executemany):
    named, written = classify(statement)
    if written:
        conn.info.setdefault(_PENDING_WRITES, set()).update(written)
    observation = _current.get()
    if observation is not None:
        observation.reads.update(named)


@event.listens_for(Engine, "commit")
def _publish_writes(conn):
    if pending := conn.info.pop(_PENDING_WRITES, None):
        versions.bump(pending)


@event.listens_for(Engine, "release_savepoint")
def _publish_released_writes(conn, name, context):
    # Not yet durable — the outer transaction may still roll back — but bumping now
    # can only invalidate entries early, and the root commit bumps the same tables
    # again, so nothing computed in between survives either.
    if pending := conn.info.get(_PENDING_WRITES):
        versions.bump(pending)


@event.listens_for(Engine, "rollback")
def _discard_writes(conn):
    # Root rollback only. A rolled-back savepoint leaves its writes pending: they
    # can't be told apart from the outer transaction's, and publishing a write
    # that didn't happen costs only a cache miss.
    conn.info.pop(_PENDING_WRITES, None)


# ==================== DAY BOUNDARIES ====================

# Supplies the timezones groups currently use. Wired to the scheduler at startup;
# the fallback covers the default zone, which is what every group starts in.
_timezone_provider: Callable[[], Iterable[str]] = lambda: (DEFAULT_TZ,)  # noqa: E731


def set_timezone_provider(provider: Callable[[], Iterable[str]]) -> None:
    global _timezone_provider
    _timezone_provider = provider


def next_day_boundary(now: datetime, zones: Iterable[str]) -> datetime:
    """The earliest upcoming local midnight across ``zones``."""
    boundaries = []
    for name in {*zones} or {DEFAULT_TZ}:
        tz = ZoneInfo(name)
        tomorrow = now.astimezone(tz).date() + timedelta(days=1)
        boundaries.append(datetime.combine(tomorrow, time(0), tz))
    return min(boundaries)


# ==================== STORE ====================


@dataclass
class Entry:
    value: Any
    deps: dict[str, int]
    expires_at: datetime
    size: int


@dataclass
class Stats:
    hits: int = 0
    misses: int = 0
    stale: int = 0
    bypassed: int = 0
    stored: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


def _entry_size(entry: Entry) -> int:
    return entry.size


class ResponseCache:
    def __init__(self, *, max_bytes: int, enabled: bool = True, clock: Callable[[], datetime] = _utcnow):
        self.enabled = enabled
        self.clock = clock
        self._lock = threading.Lock()
        self._store: LRUCache = LRUCache(maxsize=max_bytes, getsizeof=_entry_size)
        self.stats = Stats()

    def lookup(self, key: Hashable) -> Entry | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.stats.misses += 1
                return None
            if self.clock() >= entry.expires_at or not versions.current(entry.deps):
                del self._store[key]
                self.stats.stale += 1
                self.stats.misses += 1
                return None
            self.stats.hits += 1
            return entry

    def store(self, key: Hashable, value: Any, deps: dict[str, int], *, size: int,
              valid_until: datetime | None = None) -> None:
        now = self.clock()
        expires_at = next_day_boundary(now, _timezone_provider())
        if valid_until is not None:
            if valid_until <= now:
                return
            expires_at = min(expires_at, valid_until)
        entry = Entry(value=value, deps=deps, expires_at=expires_at, size=size)
        with self._lock:
            try:
                self._store[key] = entry
                self.stats.stored += 1
            except ValueError:  # larger than the whole cache
                pass

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def status(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "entries": len(self._store),
                "bytes": self._store.currsize,
                "max_bytes": self._store.maxsize,
                **self.stats.as_dict(),
            }


def _build_default() -> ResponseCache:
    from app.config import get_settings

    settings = get_settings()
    return ResponseCache(
        max_bytes=settings.RESPONSE_CACHE_MAX_MB * 1024 * 1024,
        enabled=settings.RESPONSE_CACHE_ENABLED,
    )


cache = _build_default()


# ==================== COMPUTING UNDER OBSERVATION ====================


@dataclass
class _Observation:
    before: dict[str, int]
    reads: set[str] = field(default_factory=set)
    valid_until: datetime | None = None

    def deps(self) -> dict[str, int]:
        return {t: self.before.get(t, 0) for t in self.reads}


class _observe:
    """Record the tables read inside the block, against versions taken at entry."""

    def __enter__(self) -> _Observation:
        self.observation = _Observation(before=versions.snapshot())
        self._token = _current.set(self.observation)
        return self.observation

    def __exit__(self, *exc) -> None:
        _current.reset(self._token)


def valid_until(moment: datetime) -> None:
    """Declare that the answer being computed stops being true at ``moment``.

    For results that change with the clock rather than with a write — a row that
    drops out of a query once its ``expires_at`` passes. A no-op when nothing
    cacheable is being computed, so services can call it unconditionally.
    """
    observation = _current.get()
    if observation is not None and (observation.valid_until is None or moment < observation.valid_until):
        observation.valid_until = moment


def memoize(key: Hashable, compute: Callable[[], Any], *, size: int = 256) -> Any:
    """Return ``compute()``'s value from the cache, or compute and cache it.

    The value must be plain data (it is shared between callers) and must depend
    only on the database and ``key``. Exceptions are not cached.
    """
    if not cache.enabled:
        return compute()
    if (entry := cache.lookup(key)) is not None:
        return entry.value
    with _observe() as observed:
        value = compute()
    cache.store(key, value, observed.deps(), size=size, valid_until=observed.valid_until)
    return value


# ==================== HTTP MIDDLEWARE ====================


@dataclass(frozen=True)
class CachedResponse:
    body: bytes
    content_type: bytes


def _route_template(scope: Scope) -> str | None:
    for route in scope["app"].router.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return getattr(route, "path", None)
    return None


def _viewer(scope: Scope) -> str | None:
    """The caller's identity for keying: a user id, "anon", or None to bypass.

    A request carrying a token that does not verify is passed straight through so
    the endpoint can refuse it exactly as it would without a cache.
    """
    for name, value in scope["headers"]:
        if name == b"authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            if scheme.lower() != "bearer":
                return None
            payload = decode_access_token(token)
            if payload is None or payload.get("sub") is None:
                return None
            return f"user:{payload['sub']}"
    return "anon"


class ResponseCacheMiddleware:
    """Serve ``CACHED_GETS`` responses from ``cache`` while they are still valid."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "GET" or not cache.enabled:
            await self.app(scope, receive, send)
            return
        cacheable = _route_template(scope) in CACHED_GETS
        viewer = _viewer(scope) if cacheable else None
        if viewer is None:
            if cacheable:
                cache.stats.bypassed += 1
            await self.app(scope, receive, send)
            return

        key = ("http", scope["path"], scope["query_string"], viewer)
        if (entry := cache.lookup(key)) is not None:
            await _send_cached(send, entry.value)
            return

        status, content_type, chunks = 0, b"", []

        async def capture(message: Message) -> None:
            nonlocal status, content_type
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = dict(message.get("headers", []))
                content_type = headers.get(b"content-type", b"")
                # Never cache a response that sets state on the client.
                if b"set-cookie" in headers:
                    status = -1
                message = {**message, "headers": [*message.get("headers", []), (b"x-cache", b"MISS")]}
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        with _observe() as observed:
            await self.app(scope, receive, capture)

        if status == 200:
            body = b"".join(chunks)
            cache.store(key, CachedResponse(body, content_type), observed.deps(),
                        size=len(body) + 512, valid_until=observed.valid_until)


async def _send_cached(send: Send, response: CachedResponse) -> None:
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            (b"content-type", response.content_type),
            (b"content-length", str(len(response.body)).encode()),
            (b"x-cache", b"HIT"),
        ],
    })
    await send({"type": "http.response.body", "body": response.body})
