"""Tests for get_current_user_optional: never raises, resolves to None or a User."""

import pytest
from app.dependencies import get_current_user_optional
from app.models import User
from app.utils.security import create_access_token

_DUMMY_HASH = "dummy_hash_for_testing"


@pytest.fixture
def sample_user(db_session) -> User:
    user = User(email="optional_auth@test.com", username="optional_auth_user", password_hash=_DUMMY_HASH)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestGetCurrentUserOptional:
    def test_no_token_returns_none(self, db_session):
        assert get_current_user_optional(token=None, db=db_session) is None

    def test_invalid_token_returns_none(self, db_session):
        assert get_current_user_optional(token="not-a-real-token", db=db_session) is None

    def test_valid_token_returns_user(self, db_session, sample_user):
        token = create_access_token(data={"sub": str(sample_user.id), "email": sample_user.email})
        result = get_current_user_optional(token=token, db=db_session)
        assert result is not None
        assert result.id == sample_user.id

    def test_token_for_deleted_user_returns_none(self, db_session, sample_user):
        token = create_access_token(data={"sub": str(sample_user.id), "email": sample_user.email})
        db_session.delete(sample_user)
        db_session.commit()
        assert get_current_user_optional(token=token, db=db_session) is None
