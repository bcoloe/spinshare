"""Tests for get_current_user_optional: None for a genuinely anonymous request
(no token), the User for a valid token, and 401 for a present-but-invalid token
so a client can refresh and retry rather than being silently downgraded to
anonymous (issue #140)."""

from datetime import timedelta

import pytest
from app.dependencies import get_current_user_optional
from app.models import User
from app.utils.security import create_access_token
from fastapi import HTTPException, status

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
        # A genuinely anonymous request sends no token and stays anonymous.
        assert get_current_user_optional(token=None, db=db_session) is None

    def test_valid_token_returns_user(self, db_session, sample_user):
        token = create_access_token(data={"sub": str(sample_user.id), "email": sample_user.email})
        result = get_current_user_optional(token=token, db=db_session)
        assert result is not None
        assert result.id == sample_user.id

    def test_invalid_token_raises_401(self, db_session):
        # A malformed token was sent — signal 401 rather than pretend anonymous.
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_optional(token="not-a-real-token", db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_token_raises_401(self, db_session, sample_user):
        # The #140 case: a logged-in client's 15-minute access token expires
        # mid-session. It must get a 401 (triggering a client-side refresh and
        # retry), not a 200 that reports the member as anonymous/not-in-group.
        expired = create_access_token(
            data={"sub": str(sample_user.id), "email": sample_user.email},
            expires_delta=timedelta(minutes=-1),
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_optional(token=expired, db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_for_deleted_user_raises_401(self, db_session, sample_user):
        token = create_access_token(data={"sub": str(sample_user.id), "email": sample_user.email})
        db_session.delete(sample_user)
        db_session.commit()
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_optional(token=token, db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
