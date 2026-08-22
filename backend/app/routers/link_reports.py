"""Link report router: lets any signed-in user flag a bad album link."""

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_link_report_service
from app.models import User
from app.schemas.link_report import LinkReportCreate, LinkReportResponse
from app.services.link_report_service import LinkReportService

router = APIRouter(prefix="/albums", tags=["link-reports"])


@router.post(
    "/{album_id}/link-reports",
    response_model=LinkReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_link_report(
    album_id: int,
    data: LinkReportCreate,
    current_user: User = Depends(get_current_user),
    svc: LinkReportService = Depends(get_link_report_service),
):
    """Report one of an album's links as bad, optionally suggesting a replacement.

    Requires authentication. Editing links stays admin-only; this is the path for
    everyone else to get a correction in front of an admin.
    """
    return svc.create(album_id, current_user, data)
