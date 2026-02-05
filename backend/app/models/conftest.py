"""Test configuration to support database + model tests."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base
from app.models import Album, User

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


@pytest.fixture
def sample_user(db_session) -> User:
    """Create a sample user for testing"""
    user = User(email="test@example.com", username="testuser", password_hash="hashed_password")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_album(db_session) -> Album:
    """Create a sample album for testing"""
    album = Album(
        spotify_album_id="abc123",
        title="OK Computer",
        artist="Radiohead",
        cover_url="https://example.com/cover.jpg",
        release_date="1997-05-21",
        total_tracks=12,
        genres=["alternative rock", "art rock"],
    )
    db_session.add(album)
    db_session.commit()
    db_session.refresh(album)
    return album
