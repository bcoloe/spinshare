"""Test configuration to support database + model tests."""

import random
from contextlib import nullcontext

import pytest

from app.models import Album, Genre, Group, GroupAlbum, Review, User


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
        spotify_album_id="spotify_123",
        title="OK Computer",
        artist="Radiohead",
        cover_url="https://example.com/cover.jpg",
        release_date="1997-05",
    )
    db_session.add(album)
    db_session.commit()
    db_session.refresh(album)
    return album


@pytest.fixture
def sample_genre(db_session) -> Genre:
    """Create a sample genre for testing"""
    genre = Genre(name="alternative rock")
    db_session.add(genre)
    db_session.commit()
    db_session.refresh(genre)
    return genre


class Creators:
    def __init__(self, db_session):
        self.session = db_session

    def _add_and_commit(self, to_add: str | list[str], exception: Exception | None = None):
        if isinstance(to_add, list):
            self.session.add_all(to_add)
        else:
            self.session.add(to_add)

        context = nullcontext() if exception is None else pytest.raises(exception)
        with context:
            self.session.commit()

        if exception is not None:
            self.session.rollback()

    def users(self, user_names: list[str], exception: Exception | None = None) -> list[User]:
        users = [Creators.user(name) for name in user_names]
        self._add_and_commit(users, exception)
        return users

    @staticmethod
    def user(name: str) -> User:
        return User(email=f"{name}@test.com", username=name, password_hash=f"{name}_pw")

    def group(self, name: str, creator: User, exception: Exception | None = None) -> Group:
        group = Group(name=name, created_by=creator.id, is_public=True)
        self._add_and_commit(group, exception)
        return group

    def group_album(
        self, group: Group, album: Album, added_by: User, exception: Exception | None = None
    ) -> GroupAlbum:
        group_album = GroupAlbum(group_id=group.id, album_id=album.id, added_by=added_by.id)
        self._add_and_commit(group_album, exception)
        return group_album

    def review(
        self,
        reviewer: User,
        album: Album,
        rating: int | None = None,
        comment: str | None = None,
        exception: Exception | None = None,
    ) -> Review:
        if rating is None:
            rating = 10 * random.random()
        review = Review(user_id=reviewer.id, album_id=album.id, rating=rating, comment=comment)
        self._add_and_commit(review, exception=exception)
        return review


@pytest.fixture
def creators(db_session):
    return Creators(db_session)
