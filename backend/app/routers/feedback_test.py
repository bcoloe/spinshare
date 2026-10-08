"""Router tests for POST /feedback/."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from app.routers.conftest import make_mock_user
from app.utils.github_client import GitHubIssueResult

_VALID_PAYLOAD = {
    "feedback_type": "bug",
    "title": "Something is broken here",
    "description": "When I click the button nothing happens and the page errors out.",
}

_MOCK_RESULT = GitHubIssueResult(
    number=42,
    html_url="https://github.com/owner/spinshare/issues/42",
)


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestSubmitFeedback:
    def test_submit_bug_success(self, client):
        with patch("app.routers.feedback.create_issue", return_value=_MOCK_RESULT) as mock_create:
            resp = client.post("/feedback/", json=_VALID_PAYLOAD)

        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["issue_number"] == 42
        assert data["issue_url"] == "https://github.com/owner/spinshare/issues/42"
        mock_create.assert_called_once_with(
            title=_VALID_PAYLOAD["title"],
            body=mock_create.call_args.kwargs["body"],
            label="bug",
        )

    def test_submit_feature_uses_enhancement_label(self, client):
        with patch("app.routers.feedback.create_issue", return_value=_MOCK_RESULT) as mock_create:
            resp = client.post("/feedback/", json={**_VALID_PAYLOAD, "feedback_type": "feature"})

        assert resp.status_code == status.HTTP_201_CREATED
        mock_create.assert_called_once_with(
            title=_VALID_PAYLOAD["title"],
            body=mock_create.call_args.kwargs["body"],
            label="enhancement",
        )

    def test_issue_body_includes_username_and_description(self, client, mock_user):
        with patch("app.routers.feedback.create_issue", return_value=_MOCK_RESULT) as mock_create:
            client.post("/feedback/", json=_VALID_PAYLOAD)

        body_arg = mock_create.call_args.kwargs["body"]
        assert mock_user.username in body_arg
        assert _VALID_PAYLOAD["description"] in body_arg

    def test_unauthenticated_returns_401(self, unauthed_client):
        resp = unauthed_client.post("/feedback/", json=_VALID_PAYLOAD)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_title_too_short_returns_422(self, client):
        resp = client.post("/feedback/", json={**_VALID_PAYLOAD, "title": "Brok"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_title_too_long_returns_422(self, client):
        resp = client.post("/feedback/", json={**_VALID_PAYLOAD, "title": "x" * 101})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_description_too_short_returns_422(self, client):
        resp = client.post("/feedback/", json={**_VALID_PAYLOAD, "description": "Too short"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_feedback_type_returns_422(self, client):
        resp = client.post("/feedback/", json={**_VALID_PAYLOAD, "feedback_type": "complaint"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_github_unavailable_returns_502(self, client):
        with patch(
            "app.routers.feedback.create_issue",
            side_effect=HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not create GitHub issue",
            ),
        ):
            resp = client.post("/feedback/", json=_VALID_PAYLOAD)
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY


class TestExternalFailureHandling:
    """A GitHub outage must degrade, not 500."""

    def test_transport_failure_returns_502(self, client):
        """A GitHub outage must surface as 502, not a 500 with a stack trace.

        The integration is stubbed as configured on purpose: create_issue returns
        503 "not configured" before it ever reaches httpx when GITHUB_TOKEN and
        GITHUB_REPO are unset. Relying on the ambient .env made this pass locally
        and fail in CI, which sets only DATABASE_URL and SECRET_KEY.
        """
        import httpx

        configured = SimpleNamespace(GITHUB_TOKEN="test-token", GITHUB_REPO="owner/repo")
        payload = {
            "feedback_type": "bug",
            "title": "Something is broken",
            "description": "A description that comfortably clears the minimum length.",
        }
        with (
            patch("app.utils.github_client.get_settings", return_value=configured),
            patch(
                "app.utils.github_client.httpx.post",
                side_effect=httpx.ConnectError("name resolution failed"),
            ),
        ):
            resp = client.post("/feedback/", json=payload)

        assert resp.status_code == status.HTTP_502_BAD_GATEWAY

    def test_unconfigured_integration_returns_503(self, client):
        """The other side of the same gate, pinned so the 502 test stays honest."""
        unconfigured = SimpleNamespace(GITHUB_TOKEN=None, GITHUB_REPO=None)
        payload = {
            "feedback_type": "bug",
            "title": "Something is broken",
            "description": "A description that comfortably clears the minimum length.",
        }
        with patch("app.utils.github_client.get_settings", return_value=unconfigured):
            resp = client.post("/feedback/", json=payload)

        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_an_oversized_description_is_rejected(self, client):
        """The body is relayed to GitHub verbatim, so it must be bounded."""
        payload = {
            "feedback_type": "bug",
            "title": "Something is broken",
            "description": "x" * 10_001,
        }
        resp = client.post("/feedback/", json=payload)

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
