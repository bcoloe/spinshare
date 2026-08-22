"""Business logic for user-submitted reports of bad album links.

Authority note: "admin" here always means the *site* admin flag (``users.is_admin``),
asserted by ``dependencies.get_current_admin_user``. It is unrelated to
``GroupService.is_admin()``, which is a per-group role.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Album, LinkReport, User
from app.schemas.album import validate_bandcamp_album_url, validate_wikipedia_album_url
from app.schemas.link_report import (
    ID_BASED_LINKS,
    LINK_FIELD_TO_COLUMN,
    LINK_LABELS,
    REASON_PHRASES,
    AdminLinkReportItem,
    AlbumLinksSnapshot,
    LinkReportCreate,
    LinkReportResponse,
    LinkReportStatus,
    ReportableLink,
    ReportReason,
)
from app.schemas.notification import NotificationType
from app.services.album_service import AlbumService
from app.services.notification_service import NotificationService
from app.utils.url_parser import coerce_album_identifier


class LinkReportService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create(self, album_id: int, reporter: User, data: LinkReportCreate) -> LinkReport:
        """File a report against one of an album's links.

        The suggested URL, if given, is normalised into the shape the album column
        stores so the admin's edit form can be prefilled directly. Normalisation is
        purely structural — we check the URL belongs to the right service and that an
        ID can be pulled from it, not that the album actually exists there. Verifying
        that would mean a network call per report; the admin's edit-and-save step is
        the real verification.

        Raises:
            HTTPException 400: If the suggested URL is for the wrong service or unusable
            HTTPException 404: If the album does not exist
            HTTPException 409: If this user already has an open report for this link
        """
        album = AlbumService(self.db).get_album_by_id(album_id)

        suggested_value = self._normalize_suggestion(data.link_field, data.suggested_url)

        if self._has_open_report(album_id, reporter.id, data.link_field):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an open report for this link",
            )

        report = LinkReport(
            album_id=album_id,
            reporter_id=reporter.id,
            link_field=data.link_field.value,
            reason_code=data.reason_code.value,
            reason_detail=(data.reason_detail or "").strip() or None,
            suggested_url=data.suggested_url,
            suggested_value=suggested_value,
            status=LinkReportStatus.Open.value,
        )
        self.db.add(report)
        try:
            self.db.commit()
        except IntegrityError:
            # The partial unique index is the race-safe backstop for the check above.
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an open report for this link",
            ) from None
        self.db.refresh(report)

        self._notify_admins(report, album, reporter)
        return report

    def _normalize_suggestion(
        self, link_field: ReportableLink, suggested_url: str | None
    ) -> str | None:
        """Turn a pasted URL into the value the album column stores.

        Bandcamp and Wikipedia links are stored whole and only domain-checked; the
        other three are reduced to a bare service ID.
        """
        if suggested_url is None or not suggested_url.strip():
            return None
        suggested_url = suggested_url.strip()

        try:
            if link_field == ReportableLink.Bandcamp:
                return validate_bandcamp_album_url(suggested_url)
            if link_field == ReportableLink.Wikipedia:
                return validate_wikipedia_album_url(suggested_url)
            return coerce_album_identifier(ID_BASED_LINKS[link_field], suggested_url)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from None

    def _has_open_report(
        self, album_id: int, reporter_id: int, link_field: ReportableLink
    ) -> bool:
        return (
            self.db.scalar(
                select(LinkReport.id).where(
                    LinkReport.album_id == album_id,
                    LinkReport.reporter_id == reporter_id,
                    LinkReport.link_field == link_field.value,
                    LinkReport.status == LinkReportStatus.Open.value,
                )
            )
            is not None
        )

    def _notify_admins(self, report: LinkReport, album: Album, reporter: User) -> None:
        """Tell every site admin a report has landed.

        group_id stays NULL — this notification isn't group-scoped, which is why
        the frontend routes it by type rather than by group.
        """
        admin_ids = list(
            self.db.scalars(
                select(User.id).where(
                    User.is_admin.is_(True),
                    User.is_bot.is_(False),
                    User.id != reporter.id,
                )
            ).all()
        )
        label = LINK_LABELS[ReportableLink(report.link_field)]
        phrase = REASON_PHRASES[ReportReason(report.reason_code)]
        message = (
            f"{reporter.username} reported {phrase} {label} link on "
            f"{album.title} by {album.artist}"
        )
        NotificationService(self.db).create_many(
            user_ids=admin_ids,
            type=NotificationType.link_report_submitted,
            message=message,
            album_id=album.id,
        )

    # ==================== READ ====================

    def list_reports(
        self,
        status_filter: LinkReportStatus = LinkReportStatus.Open,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminLinkReportItem]:
        """Reports of one status, newest first, with the album and reporter context.

        One query — the album join and the reporter outer-join are what let the
        queue render a row without a follow-up lookup per report.
        """
        rows = self.db.execute(
            select(LinkReport, Album, User.username)
            .join(Album, LinkReport.album_id == Album.id)
            .outerjoin(User, LinkReport.reporter_id == User.id)
            .where(LinkReport.status == status_filter.value)
            .order_by(LinkReport.created_at.desc(), LinkReport.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        items = []
        for report, album, username in rows:
            column = LINK_FIELD_TO_COLUMN[ReportableLink(report.link_field)]
            items.append(
                AdminLinkReportItem(
                    **LinkReportResponse.model_validate(report).model_dump(),
                    album=AlbumLinksSnapshot.model_validate(album),
                    reporter_username=username,
                    current_value=getattr(album, column),
                )
            )
        return items

    def count_open(self) -> int:
        """How many reports are waiting on an admin — drives the nav badge."""
        return (
            self.db.scalar(
                select(func.count(LinkReport.id)).where(
                    LinkReport.status == LinkReportStatus.Open.value
                )
            )
            or 0
        )

    def get_report(self, report_id: int) -> LinkReport:
        """Fetch a report by id.

        Raises:
            HTTPException 404: If the report does not exist
        """
        report = self.db.get(LinkReport, report_id)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Link report not found"
            )
        return report

    # ==================== UPDATE ====================

    def resolve(self, report_id: int, admin: User) -> LinkReport:
        """Mark a report resolved, closing any duplicates of the same link.

        When several people flag the same bad link, one fix settles all of them, so
        sibling open reports for the same (album, link) are closed in one statement
        rather than left for an admin to click through.

        Raises:
            HTTPException 404: If the report does not exist
            HTTPException 409: If the report has already been resolved or dismissed
        """
        report = self._close(report_id, admin, LinkReportStatus.Resolved, note=None)

        self.db.execute(
            update(LinkReport)
            .where(
                LinkReport.album_id == report.album_id,
                LinkReport.link_field == report.link_field,
                LinkReport.status == LinkReportStatus.Open.value,
            )
            .values(
                status=LinkReportStatus.Resolved.value,
                resolved_by=admin.id,
                resolved_at=report.resolved_at,
                resolution_note="Resolved alongside another report for the same link",
            )
        )
        self.db.commit()
        self.db.refresh(report)
        return report

    def dismiss(self, report_id: int, admin: User, note: str | None = None) -> LinkReport:
        """Mark a report dismissed.

        Unlike resolve, this does not cascade: judging one report unfounded says
        nothing about someone else's report of the same link.

        Raises:
            HTTPException 404: If the report does not exist
            HTTPException 409: If the report has already been resolved or dismissed
        """
        report = self._close(report_id, admin, LinkReportStatus.Dismissed, note=note)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _close(
        self,
        report_id: int,
        admin: User,
        new_status: LinkReportStatus,
        note: str | None,
    ) -> LinkReport:
        """Shared transition guard. Stages the change; the caller commits."""
        report = self.get_report(report_id)
        if report.status != LinkReportStatus.Open.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Report has already been {report.status}",
            )
        report.status = new_status.value
        report.resolved_by = admin.id
        report.resolved_at = datetime.now(timezone.utc)
        report.resolution_note = note
        return report
