"""Unit tests of User model and its relationships."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User


class TestUserModel:
    def test_create_user(self, db_session):
        """Test creating a user."""
        user = User(email="alice@example.com", username="alice", password_hash="hashed_pw")
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.email == "alice@example.com"
        assert user.created_at is not None

    def test_nonunique_username(self, db_session, sample_user: User):
        """Test that usernames must be unique."""
        user = User(
            email="unique@example.com", username=sample_user.username, password_hash="hashed_pw"
        )
        db_session.add(user)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_nonunique_username_ci(self, db_session, sample_user: User):
        """Test that username uniqueness is not case sensitive."""
        user = User(
            email="unique@example.com",
            username=sample_user.username.upper(),
            password_hash="hashed_pw",
        )
        db_session.add(user)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_nonunique_email(self, db_session, sample_user: User):
        """Test that user emails must be unique."""
        user = User(email=sample_user.email, username="unique", password_hash="hashed_pw")
        db_session.add(user)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_nonunique_email_ci(self, db_session, sample_user: User):
        """Test that unique email condition is not case-sensitive."""
        user = User(email=sample_user.email.upper(), username="unique", password_hash="hashed_pw")
        db_session.add(user)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_persists_to_database(self, db_session, sample_user):
        """Test that user data is actually saved to and retrievable from database"""
        db_session.add(sample_user)
        db_session.commit()
        user_id = sample_user.id

        # Close the session and create a new one to simulate new request.
        db_session.close()

        # Query in fresh session
        fresh_user = db_session.query(User).filter(User.id == user_id).first()

        assert fresh_user is not None
        assert fresh_user.email == "test@example.com"
        assert fresh_user.username == "testuser"
        assert fresh_user.password_hash == "hashed_password"
        assert fresh_user.created_at is not None
