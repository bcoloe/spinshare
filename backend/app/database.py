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
engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency for routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
