"""Base application test configuration + figures"""

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


@pytest.fixture(scope="function")
def engine(test_settings):
    """Create a test database engine"""
    engine = create_engine(test_settings.DATABASE_URL)
    Base.metadata.create_all(bind=engine)  # Create all tables
    yield engine
    Base.metadata.drop_all(bind=engine)  # Clean up after test
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a new database session for a test"""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
