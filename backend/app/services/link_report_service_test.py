"""Tests for LinkReportService."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException, status

from app.models import Album, LinkReport, Notification
from app.schemas.link_report import (
    LINK_FIELD_TO_COLUMN,
    LinkReportCreate,
    LinkReportStatus,
    ReportableLink,
    ReportReason,
)
from app.schemas.notification import NotificationType
from app.utils.url_parser import MusicService

SPOTIFY_URL = "https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR?si=6f2aaf776e7a4eab"


def _create(
    link_field=ReportableLink.Spotify,
    reason_code=ReportReason.Bad,
    reason_detail=None,
    url=None,
):
    return LinkReportCreate(
        link_field=link_field,
        reason_code=reason_code,
        reason_detail=reason_detail,
        suggested_url=url,
    )


class TestLinkFieldMapping:
    def test_music_service_values_are_reportable_links(self):
        """detect_service output must compare 1:1 against link_field with no translation."""
        reportable = {link.value for link in ReportableLink}
        for service in MusicService:
            assert service.value in reportable

    def test_every_link_field_maps_to_a_real_album_column(self):
        for link in ReportableLink:
            assert link in LINK_FIELD_TO_COLUMN
            assert hasattr(Album, LINK_FIELD_TO_COLUMN[link])


class TestCreateLinkReport:
    def test_create_success_persists_row(self, link_report_service, sample_album, sample_user):
        report = link_report_service.create(sample_album.id, sample_user, _create())

        assert report.id is not None
        assert report.album_id == sample_album.id
        assert report.reporter_id == sample_user.id
        assert report.link_field == ReportableLink.Spotify.value
        assert report.status == LinkReportStatus.Open.value
        assert report.reason_code == ReportReason.Bad.value
        assert report.suggested_value is None

    def test_create_unknown_album_raises_404(self, link_report_service, sample_user):
        with pytest.raises(HTTPException) as exc_info:
            link_report_service.create(999999, sample_user, _create())
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_create_duplicate_open_raises_409(
        self, link_report_service, sample_album, sample_user
    ):
        link_report_service.create(sample_album.id, sample_user, _create())

        with pytest.raises(HTTPException) as exc_info:
            link_report_service.create(sample_album.id, sample_user, _create())
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_create_allows_report_on_a_different_link(
        self, link_report_service, sample_album, sample_user
    ):
        link_report_service.create(sample_album.id, sample_user, _create())
        second = link_report_service.create(
            sample_album.id, sample_user, _create(link_field=ReportableLink.AppleMusic)
        )
        assert second.id is not None

    def test_create_normalizes_spotify_url_to_id(
        self, link_report_service, sample_album, sample_user
    ):
        report = link_report_service.create(
            sample_album.id, sample_user, _create(url=SPOTIFY_URL)
        )

        assert report.suggested_url == SPOTIFY_URL  # raw, as pasted
        assert report.suggested_value == "3v1nspBDZhlcJGDW6fUJQR"  # normalized

    def test_create_normalizes_apple_music_url_to_id(
        self, link_report_service, sample_album, sample_user
    ):
        report = link_report_service.create(
            sample_album.id,
            sample_user,
            _create(
                link_field=ReportableLink.AppleMusic,
                url="https://music.apple.com/us/album/ok-computer/1097862703",
            ),
        )
        assert report.suggested_value == "1097862703"

    def test_create_normalizes_youtube_music_url(
        self, link_report_service, sample_album, sample_user
    ):
        report = link_report_service.create(
            sample_album.id,
            sample_user,
            _create(
                link_field=ReportableLink.YouTubeMusic,
                url="https://music.youtube.com/browse/MPREb_abc123",
            ),
        )
        assert report.suggested_value == "MPREb_abc123"

    def test_create_keeps_bandcamp_url_verbatim(
        self, link_report_service, sample_album, sample_user
    ):
        url = "https://radiohead.bandcamp.com/album/ok-computer"
        report = link_report_service.create(
            sample_album.id, sample_user, _create(link_field=ReportableLink.Bandcamp, url=url)
        )
        assert report.suggested_value == url

    def test_create_keeps_wikipedia_url_verbatim(
        self, link_report_service, sample_album, sample_user
    ):
        url = "https://en.wikipedia.org/wiki/OK_Computer"
        report = link_report_service.create(
            sample_album.id, sample_user, _create(link_field=ReportableLink.Wikipedia, url=url)
        )
        assert report.suggested_value == url

    def test_create_rejects_wrong_service_for_link_field_400(
        self, link_report_service, sample_album, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            link_report_service.create(
                sample_album.id,
                sample_user,
                _create(url="https://music.apple.com/us/album/ok-computer/1097862703"),
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Apple Music" in exc_info.value.detail

    def test_create_rejects_non_wikipedia_url_400(
        self, link_report_service, sample_album, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            link_report_service.create(
                sample_album.id,
                sample_user,
                _create(link_field=ReportableLink.Wikipedia, url="https://evil.example.com/x"),
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_rejects_non_bandcamp_url_400(
        self, link_report_service, sample_album, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            link_report_service.create(
                sample_album.id,
                sample_user,
                _create(link_field=ReportableLink.Bandcamp, url="https://evil.example.com/album/x"),
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_notifies_all_admins(
        self, db_session, link_report_service, sample_album, sample_user, user_factory
    ):
        admins = [
            user_factory(email=f"a{i}@test.com", username=f"admin{i}") for i in range(2)
        ]
        for a in admins:
            a.is_admin = True
        db_session.commit()

        link_report_service.create(sample_album.id, sample_user, _create())

        notes = db_session.query(Notification).all()
        assert {n.user_id for n in notes} == {a.id for a in admins}
        assert all(n.type == NotificationType.link_report_submitted for n in notes)
        assert all(n.album_id == sample_album.id for n in notes)
        assert all(n.group_id is None for n in notes)
        assert sample_user.username in notes[0].message

    def test_create_excludes_bots_and_self_from_notification(
        self, db_session, link_report_service, sample_album, user_factory
    ):
        admin_reporter = user_factory(email="ar@test.com", username="adminreporter")
        admin_reporter.is_admin = True
        bot_admin = user_factory(email="bot@test.com", username="botadmin")
        bot_admin.is_admin = True
        bot_admin.is_bot = True
        db_session.commit()

        link_report_service.create(sample_album.id, admin_reporter, _create())

        # The only admins are the reporter themselves and a bot — nobody to tell.
        assert db_session.query(Notification).count() == 0

    def test_create_makes_no_network_calls(
        self, link_report_service, sample_album, sample_user
    ):
        """Submitting a report must be one cheap DB write, never a service lookup."""
        with patch("httpx.get") as mock_get, patch("httpx.Client") as mock_client:
            link_report_service.create(sample_album.id, sample_user, _create(url=SPOTIFY_URL))
        mock_get.assert_not_called()
        mock_client.assert_not_called()


class TestReportReason:
    def test_detail_is_optional(self, link_report_service, sample_album, sample_user):
        report = link_report_service.create(
            sample_album.id, sample_user, _create(reason_code=ReportReason.Missing)
        )

        assert report.reason_code == ReportReason.Missing.value
        assert report.reason_detail is None

    def test_detail_is_stored_when_given(
        self, link_report_service, sample_album, sample_user
    ):
        report = link_report_service.create(
            sample_album.id,
            sample_user,
            _create(reason_code=ReportReason.Other, reason_detail="Region-locked for me."),
        )

        assert report.reason_detail == "Region-locked for me."

    def test_blank_detail_is_normalised_to_none(
        self, link_report_service, sample_album, sample_user
    ):
        """Whitespace-only prose is not detail — store NULL so the queue stays clean."""
        report = link_report_service.create(
            sample_album.id, sample_user, _create(reason_detail="   ")
        )

        assert report.reason_detail is None

    @pytest.mark.parametrize(
        "reason_code,expected",
        [
            (ReportReason.Missing, "a missing"),
            (ReportReason.Bad, "a broken"),
            (ReportReason.Other, "an issue with the"),
        ],
    )
    def test_notification_wording_follows_the_reason(
        self,
        db_session,
        link_report_service,
        sample_album,
        sample_user,
        user_factory,
        reason_code,
        expected,
    ):
        admin = user_factory(email="na@test.com", username="notifyadmin")
        admin.is_admin = True
        db_session.commit()

        link_report_service.create(
            sample_album.id, sample_user, _create(reason_code=reason_code)
        )

        message = db_session.query(Notification).one().message
        assert f"reported {expected} Spotify link" in message


class TestListReports:
    def test_defaults_to_open_only(
        self, link_report_service, sample_album, sample_user, user_factory
    ):
        other = user_factory(email="o@test.com", username="other")
        open_report = link_report_service.create(sample_album.id, sample_user, _create())
        link_report_service.create(sample_album.id, other, _create())
        link_report_service.dismiss(open_report.id, other, note="fine actually")

        items = link_report_service.list_reports()

        assert len(items) == 1
        assert items[0].reporter_username == "other"

    def test_filters_by_status(
        self, link_report_service, sample_album, sample_user, admin_user
    ):
        report = link_report_service.create(sample_album.id, sample_user, _create())
        link_report_service.dismiss(report.id, admin_user, note="not a problem")

        assert link_report_service.list_reports(LinkReportStatus.Open) == []
        dismissed = link_report_service.list_reports(LinkReportStatus.Dismissed)
        assert len(dismissed) == 1
        assert dismissed[0].resolution_note == "not a problem"

    def test_orders_newest_first(
        self, link_report_service, sample_album, sample_user, user_factory
    ):
        first = link_report_service.create(sample_album.id, sample_user, _create())
        other = user_factory(email="o2@test.com", username="other2")
        second = link_report_service.create(sample_album.id, other, _create())

        items = link_report_service.list_reports()

        assert [i.id for i in items] == [second.id, first.id]

    def test_includes_album_snapshot_and_current_value(
        self, link_report_service, sample_album, sample_user
    ):
        link_report_service.create(sample_album.id, sample_user, _create())

        item = link_report_service.list_reports()[0]

        assert item.album.title == sample_album.title
        assert item.album.artist == sample_album.artist
        assert item.current_value == sample_album.spotify_album_id

    def test_missing_reporter_renders_none(
        self, db_session, link_report_service, sample_album, sample_user
    ):
        link_report_service.create(sample_album.id, sample_user, _create())
        db_session.delete(sample_user)
        db_session.commit()

        item = link_report_service.list_reports()[0]

        assert item.reporter_username is None
        assert item.reporter_id is None

    def test_respects_limit_and_offset(
        self, link_report_service, sample_album, sample_user, user_factory
    ):
        link_report_service.create(sample_album.id, sample_user, _create())
        other = user_factory(email="o3@test.com", username="other3")
        link_report_service.create(sample_album.id, other, _create())

        assert len(link_report_service.list_reports(limit=1)) == 1
        assert len(link_report_service.list_reports(limit=1, offset=1)) == 1
        assert link_report_service.list_reports(limit=1, offset=2) == []


class TestResolve:
    def test_resolve_sets_status_admin_and_timestamp(
        self, link_report_service, sample_album, sample_user, admin_user
    ):
        report = link_report_service.create(sample_album.id, sample_user, _create())

        resolved = link_report_service.resolve(report.id, admin_user)

        assert resolved.status == LinkReportStatus.Resolved.value
        assert resolved.resolved_by == admin_user.id
        assert resolved.resolved_at is not None

    def test_resolve_cascades_to_sibling_open_reports_for_same_link(
        self, db_session, link_report_service, sample_album, sample_user, user_factory, admin_user
    ):
        mine = link_report_service.create(sample_album.id, sample_user, _create())
        other = user_factory(email="o4@test.com", username="other4")
        theirs = link_report_service.create(sample_album.id, other, _create())

        link_report_service.resolve(mine.id, admin_user)

        db_session.refresh(theirs)
        assert theirs.status == LinkReportStatus.Resolved.value
        assert theirs.resolved_by == admin_user.id

    def test_resolve_does_not_touch_other_link_fields(
        self, db_session, link_report_service, sample_album, sample_user, admin_user
    ):
        spotify = link_report_service.create(sample_album.id, sample_user, _create())
        apple = link_report_service.create(
            sample_album.id, sample_user, _create(link_field=ReportableLink.AppleMusic)
        )

        link_report_service.resolve(spotify.id, admin_user)

        db_session.refresh(apple)
        assert apple.status == LinkReportStatus.Open.value

    def test_resolve_does_not_touch_other_albums(
        self, db_session, link_report_service, sample_album, sample_user, admin_user
    ):
        other_album = Album(spotify_album_id="spotify_other", title="Kid A", artist="Radiohead")
        db_session.add(other_album)
        db_session.commit()

        mine = link_report_service.create(sample_album.id, sample_user, _create())
        elsewhere = link_report_service.create(other_album.id, sample_user, _create())

        link_report_service.resolve(mine.id, admin_user)

        db_session.refresh(elsewhere)
        assert elsewhere.status == LinkReportStatus.Open.value

    def test_resolve_already_resolved_raises_409(
        self, link_report_service, sample_album, sample_user, admin_user
    ):
        report = link_report_service.create(sample_album.id, sample_user, _create())
        link_report_service.resolve(report.id, admin_user)

        with pytest.raises(HTTPException) as exc_info:
            link_report_service.resolve(report.id, admin_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_resolve_not_found_404(self, link_report_service, admin_user):
        with pytest.raises(HTTPException) as exc_info:
            link_report_service.resolve(999999, admin_user)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestDismiss:
    def test_dismiss_sets_status_and_note(
        self, link_report_service, sample_album, sample_user, admin_user
    ):
        report = link_report_service.create(sample_album.id, sample_user, _create())

        dismissed = link_report_service.dismiss(report.id, admin_user, note="link works for me")

        assert dismissed.status == LinkReportStatus.Dismissed.value
        assert dismissed.resolution_note == "link works for me"
        assert dismissed.resolved_by == admin_user.id

    def test_dismiss_does_not_cascade(
        self, db_session, link_report_service, sample_album, sample_user, user_factory, admin_user
    ):
        """One admin's judgement shouldn't silently close someone else's report."""
        mine = link_report_service.create(sample_album.id, sample_user, _create())
        other = user_factory(email="o5@test.com", username="other5")
        theirs = link_report_service.create(sample_album.id, other, _create())

        link_report_service.dismiss(mine.id, admin_user, note="nope")

        db_session.refresh(theirs)
        assert theirs.status == LinkReportStatus.Open.value

    def test_dismiss_already_closed_raises_409(
        self, link_report_service, sample_album, sample_user, admin_user
    ):
        report = link_report_service.create(sample_album.id, sample_user, _create())
        link_report_service.dismiss(report.id, admin_user)

        with pytest.raises(HTTPException) as exc_info:
            link_report_service.dismiss(report.id, admin_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_dismiss_not_found_404(self, link_report_service, admin_user):
        with pytest.raises(HTTPException) as exc_info:
            link_report_service.dismiss(999999, admin_user)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_dismissed_link_can_be_reported_again(
        self, link_report_service, sample_album, sample_user, admin_user
    ):
        """The unique index is partial, so closing frees the slot."""
        report = link_report_service.create(sample_album.id, sample_user, _create())
        link_report_service.dismiss(report.id, admin_user)

        again = link_report_service.create(sample_album.id, sample_user, _create())
        assert again.id != report.id


class TestCountOpen:
    def test_counts_only_open(
        self, link_report_service, sample_album, sample_user, user_factory, admin_user
    ):
        assert link_report_service.count_open() == 0

        first = link_report_service.create(sample_album.id, sample_user, _create())
        other = user_factory(email="o6@test.com", username="other6")
        link_report_service.create(
            sample_album.id, other, _create(link_field=ReportableLink.Wikipedia)
        )
        assert link_report_service.count_open() == 2

        link_report_service.dismiss(first.id, admin_user)
        assert link_report_service.count_open() == 1
