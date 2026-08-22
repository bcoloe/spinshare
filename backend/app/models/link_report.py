"""Link report table — user-submitted flags on bad album links.

Album links are five flat columns on ``albums`` rather than rows in a link
table, so a report names the column it is about via ``link_field`` (see
``ReportableLink`` in ``app.schemas.link_report``).

Report lifecycle:
  - status == "open"      → awaiting an admin
  - status == "resolved"  → an admin corrected the link
  - status == "dismissed" → an admin judged the link fine as-is

``reporter_id`` is nullable with ``ON DELETE SET NULL``, mirroring
``messages.user_id``: a dead link is still dead after the person who flagged
it deletes their account, so the report outlives the reporter.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class LinkReport(Base):
    __tablename__ = "link_reports"

    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(
        Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Which of the album's link columns this report is about — a ReportableLink value.
    link_field = Column(String, nullable=False)
    # A ReportReason value (missing / bad / other) rather than free text, so the
    # queue can be scanned and filtered. reason_detail is optional elaboration.
    reason_code = Column(String, nullable=False)
    reason_detail = Column(Text, nullable=True)
    # The URL exactly as the reporter pasted it, kept for admin context.
    suggested_url = Column(String, nullable=True)
    # suggested_url normalised into the shape the album column stores (a bare
    # service ID for spotify/apple/ytm, the full URL for bandcamp/wikipedia).
    # This is what prefills the admin's edit form.
    suggested_value = Column(String, nullable=True)

    status = Column(String, nullable=False, server_default="open")
    resolved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    album = relationship("Album")
    reporter = relationship("User", foreign_keys=[reporter_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

    __table_args__ = (
        # The queue reads "open reports, newest first", and the nav badge counts
        # open rows — this index serves both.
        Index("ix_link_reports_status_created", "status", "created_at"),
        # One *open* report per person per link. Partial so that once a report is
        # resolved or dismissed the same user may flag the link again later, which
        # is legitimate: links rot more than once.
        Index(
            "uq_link_reports_open_per_user",
            "album_id",
            "reporter_id",
            "link_field",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )
