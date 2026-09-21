"""Base application test configuration + figures"""

import datetime
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base

# Set testing environment variable.
os.environ["TESTING"] = "1"


@pytest.fixture(scope="session")
def test_settings():
    """Provide test settings"""
    return get_settings(env_file=".env.test")


@pytest.fixture(scope="session")
def engine(test_settings):
    """Create a test database engine — tables created once per session, isolation via db_session rollback."""
    engine = create_engine(test_settings.DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a new database session for a test.

    ``join_transaction_mode="create_savepoint"`` is what makes the outer
    ``transaction.rollback()`` below actually undo the test. Without it, the
    Session adopts the connection's existing transaction directly, so the first
    ``session.rollback()`` from code under test deassociates that transaction —
    SQLAlchemy even warns "transaction already deassociated from connection" —
    and everything written afterwards is committed for real. The teardown
    rollback then has nothing left to undo and the rows leak into later tests.

    That bites precisely the tests worth having: any service path that rolls
    back (IntegrityError handling, create_group's all-or-nothing sequence).
    Pinning the mode keeps the Session on savepoints, so its commits and
    rollbacks stay nested inside the transaction this fixture controls.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def fake_now():
    """Create a fake now response."""
    return datetime.datetime(2016, 1, 13, tzinfo=datetime.UTC)


@pytest.fixture(scope="function")
def test_password() -> str:
    return "a-Fine-Password123!"
