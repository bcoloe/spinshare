from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_group_service
from app.main import app
from app.models import Group, User
from app.services.group_service import GroupService
from app.utils.security import create_access_token


# ==================== USER HELPERS ====================

def make_mock_user(id=1, email="user@test.com", username="test_user") -> MagicMock:
    user = MagicMock(spec=User)
    user.id = id
    user.email = email
    user.username = username
    return user


def _auth_headers_for(user) -> dict:
    """Generate Bearer auth headers for a given user without hitting the DB."""
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


# ==================== GROUP HELPERS ====================

def make_mock_group(
    id=1,
    name="Bumblebees",
    is_public=True,
    members=None,
    albums=None,
    created_at=None,
) -> MagicMock:
    group = MagicMock(spec=Group)
    group.id = id
    group.name = name
    group.is_public = is_public
    group.members = members if members is not None else []
    group.albums = albums if albums is not None else []
    group.created_at = created_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return group


# ==================== FIXTURES ====================

@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def mock_group_service():
    return MagicMock(spec=GroupService)


@pytest.fixture
def client(mock_user, mock_group_service):
    """Authenticated TestClient with the group service fully mocked."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_group_service] = lambda: mock_group_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_group_service):
    """Unauthenticated TestClient (service still mocked to isolate auth checks)."""
    app.dependency_overrides[get_group_service] = lambda: mock_group_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
