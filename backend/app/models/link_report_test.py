"""Model-level tests for LinkReport — constraints and FK behaviour against the real DB."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Album, LinkReport, User


def _report(album: Album, reporter: User | None, link_field: str = "spotify", **kwargs) -> LinkReport:
    return LinkReport(
        album_id=album.id,
        reporter_id=reporter.id if reporter else None,
        link_field=link_field,
        reason_code="bad",
        **kwargs,
    )


class TestLinkReportConstraints:
    def test_duplicate_open_report_same_user_link_violates_unique(
        self, db_session, sample_album, sample_user
    ):
        db_session.add(_report(sample_album, sample_user))
        db_session.commit()

        db_session.add(_report(sample_album, sample_user))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_same_user_may_report_a_different_link_on_the_same_album(
        self, db_session, sample_album, sample_user
    ):
        db_session.add(_report(sample_album, sample_user, link_field="spotify"))
        db_session.add(_report(sample_album, sample_user, link_field="apple_music"))
        db_session.commit()

        assert len(db_session.scalars(select(LinkReport)).all()) == 2

    def test_second_report_allowed_after_first_resolved(
        self, db_session, sample_album, sample_user
    ):
        first = _report(sample_album, sample_user)
        db_session.add(first)
        db_session.commit()

        # The partial index only covers open rows, so closing the first frees the slot.
        first.status = "resolved"
        db_session.commit()

        db_session.add(_report(sample_album, sample_user))
        db_session.commit()

        assert len(db_session.scalars(select(LinkReport)).all()) == 2

    def test_different_users_may_both_report_same_link(
        self, db_session, sample_album, creators
    ):
        alice, bob = creators.users(["alice", "bob"])
        db_session.add(_report(sample_album, alice))
        db_session.add(_report(sample_album, bob))
        db_session.commit()

        assert len(db_session.scalars(select(LinkReport)).all()) == 2

    def test_album_delete_cascades_reports(self, db_session, sample_album, sample_user):
        db_session.add(_report(sample_album, sample_user))
        db_session.commit()

        db_session.delete(sample_album)
        db_session.commit()

        assert db_session.scalars(select(LinkReport)).all() == []

    def test_reporter_delete_nulls_reporter_id_and_keeps_report(
        self, db_session, sample_album, sample_user
    ):
        db_session.add(_report(sample_album, sample_user))
        db_session.commit()

        db_session.delete(sample_user)
        db_session.commit()

        reports = db_session.scalars(select(LinkReport)).all()
        assert len(reports) == 1
        assert reports[0].reporter_id is None

    def test_status_defaults_to_open(self, db_session, sample_album, sample_user):
        report = _report(sample_album, sample_user)
        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)

        assert report.status == "open"
        assert report.created_at is not None
        assert report.resolved_at is None
