"""Feedback router: accepts user-submitted feedback and creates a GitHub issue."""

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.models import User
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.utils.github_client import create_issue

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Maps the user-facing feedback_type to the GitHub issue label.
_LABEL_MAP = {"bug": "bug", "feature": "enhancement"}


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
):
    """Submit user feedback as a GitHub issue.

    Requires authentication. Creates a GitHub issue in the configured repository
    with label "bug" or "enhancement" based on feedback_type.
    """
    label = _LABEL_MAP[data.feedback_type]
    body = f"**Submitted by:** @{current_user.username}\n\n{data.description}"
    result = create_issue(title=data.title, body=body, label=label)
    return FeedbackResponse(issue_number=result.number, issue_url=result.html_url)
