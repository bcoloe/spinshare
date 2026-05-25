"""Router tests for POST /feedback/."""

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
