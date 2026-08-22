"""Admin router: the site-admin panel's backing endpoints.

Every route here is gated on ``get_current_admin_user`` — site admin
(``users.is_admin``), not the per-group role of the same name.
"""

from fastapi import APIRouter, Depends, Query

from app.dependencies import (
    get_admin_service,
    get_current_admin_user,
    get_link_report_service,
)
from app.models import User
from app.schemas.admin import AdminMetricsResponse
from app.schemas.link_report import (
    AdminLinkReportItem,
    LinkReportCountResponse,
    LinkReportResolve,
    LinkReportResponse,
    LinkReportStatus,
)
from app.services.admin_service import AdminService
from app.services.link_report_service import LinkReportService

router = APIRouter(prefix="/admin", tags=["admin"])


# Declared before /link-reports/{report_id}/... so "count" is never captured as an id.
@router.get("/link-reports/count", response_model=LinkReportCountResponse)
def get_open_link_report_count(
    _admin: User = Depends(get_current_admin_user),
    svc: LinkReportService = Depends(get_link_report_service),
):
    """How many link reports are awaiting review. Requires admin privileges."""
    return LinkReportCountResponse(open_count=svc.count_open())


@router.get("/link-reports", response_model=list[AdminLinkReportItem])
def list_link_reports(
    status_filter: LinkReportStatus = Query(LinkReportStatus.Open, alias="status"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: User = Depends(get_current_admin_user),
    svc: LinkReportService = Depends(get_link_report_service),
):
    """The link report queue, newest first. Requires admin privileges."""
    return svc.list_reports(status_filter=status_filter, limit=limit, offset=offset)


@router.post("/link-reports/{report_id}/resolve", response_model=LinkReportResponse)
def resolve_link_report(
    report_id: int,
    admin: User = Depends(get_current_admin_user),
    svc: LinkReportService = Depends(get_link_report_service),
):
    """Mark a report resolved, closing duplicates of the same link.

    Called after the admin has actually corrected the link via PATCH /albums/{id}.
    """
    return svc.resolve(report_id, admin)


@router.post("/link-reports/{report_id}/dismiss", response_model=LinkReportResponse)
def dismiss_link_report(
    report_id: int,
    body: LinkReportResolve,
    admin: User = Depends(get_current_admin_user),
    svc: LinkReportService = Depends(get_link_report_service),
):
    """Reject a report without changing the album. Requires admin privileges."""
    return svc.dismiss(report_id, admin, body.note)


@router.get("/metrics", response_model=AdminMetricsResponse)
def get_admin_metrics(
    days: int = Query(30, ge=1, le=365),
    _admin: User = Depends(get_current_admin_user),
    svc: AdminService = Depends(get_admin_service),
):
    """Site growth and recency metrics over the last `days`.

    Content statistics (top albums, most-nominated artists, platform totals) come
    from GET /explore/stats instead — this covers only what that endpoint lacks.
    """
    return svc.get_admin_metrics(days)
