"""Database creation logic."""

import threading

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ── Optional DB query counter (dev/benchmarking only) ─────────────────────────
# Enable via TRACK_DB_QUERIES=true in .env. Counts raw cursor executions so you
# can see how many DB round-trips the cache saves during simulate_traffic.py runs.
_db_query_count: int = 0
_db_lock = threading.Lock()


def get_db_query_count() -> int:
    return _db_query_count


def reset_db_query_count() -> None:
    global _db_query_count
    with _db_lock:
        _db_query_count = 0


if settings.TRACK_DB_QUERIES:
    @event.listens_for(engine, "before_cursor_execute")
    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        global _db_query_count
        with _db_lock:
            _db_query_count += 1


# ── Dependency for routes ──────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
