"""Database creation logic."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# NullPool closes every connection immediately after use so Neon's serverless compute
# can auto-suspend between requests. Combined with Neon's built-in PgBouncer pooler
# (port 6543), this gives fast connection acquisition without holding backend processes
# open. pool_pre_ping is omitted — it has no effect with NullPool and adds latency.
# connect_timeout caps DNS/TCP failures at 5 s so transient Neon outages surface
# quickly as OperationalError (→ 503) rather than hanging indefinitely.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    poolclass=NullPool,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency for routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
