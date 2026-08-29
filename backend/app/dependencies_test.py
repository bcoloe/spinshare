"""Tests for the authentication dependencies.

get_current_user_optional: None for a genuinely anonymous request (no token),
the User for a valid token, and 401 for a present-but-invalid token so a client
can refresh and retry rather than being silently downgraded to anonymous
(issue #140).

get_socket_identity: the same auth boundary, answered from token claims without
a database read, because a reconnecting chat client hits it continuously.
"""

from datetime import timedelta

import pytest
from fastapi import HTTPException, status

from app.dependencies import get_current_user_optional, get_socket_identity
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


class TestGetSocketIdentity:
    """The chat ticket's auth boundary, which must not touch the database."""

    def test_reads_identity_from_token_claims_without_a_lookup(self, db_session):
        token = create_access_token(
            data={
                "sub": "42",
                "email": "claims@test.com",
                "username": "claims_user",
                "groups": [3, 1],
            }
        )

        # A None session stands in for "no database available at all". If the
        # fast path ever regresses into a lookup, this raises instead of passing
        # quietly against a working session.
        identity = get_socket_identity(token=token, db=None)

        assert identity.user_id == 42
        assert identity.username == "claims_user"
        assert identity.group_ids == [3, 1]

    def test_falls_back_to_the_database_for_a_legacy_token(self, db_session, sample_user):
        """Sessions already in flight at deploy time carry no identity claims."""
        token = create_access_token(data={"sub": str(sample_user.id), "email": sample_user.email})

        identity = get_socket_identity(token=token, db=db_session)

        assert identity.user_id == sample_user.id
        assert identity.username == sample_user.username
        assert identity.group_ids == []

    def test_malformed_group_claim_is_rejected_rather_than_trusted(self, db_session):
        token = create_access_token(
            data={"sub": "42", "username": "claims_user", "groups": ["not-an-id"]}
        )

        with pytest.raises(HTTPException) as exc_info:
            get_socket_identity(token=token, db=db_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_is_rejected(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            get_socket_identity(token="not-a-token", db=db_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_without_a_subject_is_rejected(self, db_session):
        token = create_access_token(data={"email": "nosub@test.com"})

        with pytest.raises(HTTPException) as exc_info:
            get_socket_identity(token=token, db=db_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
