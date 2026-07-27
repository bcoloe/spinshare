"""Model tests for GroupParticipation."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Group, GroupAlbum, GroupParticipation, PriorityReviewCredit


@pytest.fixture
def sample_group(db_session, sample_user) -> Group:
    group = Group(name="Test Group", created_by=sample_user.id, is_public=True)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    return group


class TestGroupParticipation:
    def test_defaults_and_persist(self, db_session, sample_group, sample_user):
        row = GroupParticipation(group_id=sample_group.id, user_id=sample_user.id)
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)

        assert row.id is not None
        assert row.credits == 0
        assert row.priority_group_album_id is None
        assert row.priority_queued_at is None

    def test_unique_per_group_user(self, db_session, sample_group, sample_user):
        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id))
        db_session.commit()

        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_priority_album_relationship(self, db_session, sample_group, sample_user, sample_album):
        ga = GroupAlbum(group_id=sample_group.id, album_id=sample_album.id, added_by=sample_user.id)
        db_session.add(ga)
        db_session.commit()

        row = GroupParticipation(
            group_id=sample_group.id, user_id=sample_user.id, priority_group_album_id=ga.id
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)

        assert row.priority_group_album is not None
        assert row.priority_group_album.id == ga.id

    def test_cascade_on_group_delete(self, db_session, sample_group, sample_user):
        db_session.add(GroupParticipation(group_id=sample_group.id, user_id=sample_user.id))
        db_session.commit()

        db_session.delete(sample_group)
        db_session.commit()

        remaining = (
            db_session.query(GroupParticipation)
            .filter(GroupParticipation.group_id == sample_group.id)
            .count()
        )
        assert remaining == 0


class TestPriorityReviewCredit:
    def test_unique_per_group_user_album(self, db_session, sample_group, sample_user, sample_album):
        db_session.add(PriorityReviewCredit(
            group_id=sample_group.id, user_id=sample_user.id, album_id=sample_album.id
        ))
        db_session.commit()

        db_session.add(PriorityReviewCredit(
            group_id=sample_group.id, user_id=sample_user.id, album_id=sample_album.id
        ))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
