import random
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from app.models import Album, BotSource, GroupAlbum, Review, User
from app.models.group import Group, GroupRole, group_members
from app.models.group_settings import GroupSettings
from app.schemas.group import GroupCreate, GroupModifyRequest, GroupSettingsUpdate
from app.schemas.notification import NotificationType
from app.services.notification_service import NotificationService
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError, OperationalError


class TestGroupServiceCreate:
    def test_create_group_successful(self, sample_group_service, sample_user):
        """Test successful creation of a new group"""
        group_data = GroupCreate(name="Bumblebees")
        group = sample_group_service.create_group(group_data, sample_user)

        assert group is not None
        assert group.id is not None
        assert group.name == group_data.name
        assert group.name_uniform == group_data.name.lower()
        assert group.created_by == sample_user.id
        assert group.created_at is not None
        assert group.creator == sample_user
        assert group.is_public
        assert sample_user in group.members
        assert sample_group_service.get_user_role(sample_user.id, group.id) == GroupRole.Owner

    def test_create_group_successful_private(self, sample_group_service, sample_user):
        """Test successful creation of a new group"""
        group_data = GroupCreate(name="Bumblebees", is_public=False)
        group = sample_group_service.create_group(group_data, sample_user)

        assert group is not None
        assert group.id is not None
        assert group.name == group_data.name
        assert group.name_uniform == group_data.name.lower()
        assert group.created_by == sample_user.id
        assert group.created_at is not None
        assert group.creator == sample_user
        assert not group.is_public
        assert sample_user in group.members
        assert sample_group_service.get_user_role(sample_user.id, group.id) == GroupRole.Owner

    @pytest.mark.parametrize(
        "group_name_case",
        [
            ("",),
            ("lower",),
            ("upper",),
            ("title",),
            ("random",),
        ],
    )
    def test_create_group_conflict(
        self, sample_group_service, sample_user, sample_group, group_name_case
    ):
        """Test that creating a group whose name is already taken results in a conflict."""
        new_group_name = sample_group.name
        if group_name_case == "lower":
            new_group_name = new_group_name.lower()
        elif group_name_case == "upper":
            new_group_name = new_group_name.upper()
        elif group_name_case == "title":
            new_group_name = new_group_name.title()
        elif group_name_case == "random":
            new_group_name = "".join(
                [x.upper() if random.random() > 0.5 else x.lower() for x in new_group_name]
            )

        group_data = GroupCreate(name=new_group_name)
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.create_group(group_data, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "Group name already registered"

    def test_create_group_creates_settings(self, sample_group_service, sample_user, db_session):
        """Settings land in the same transaction as the group.

        A group without GroupSettings 404s on every daily selection and dealer roll.
        """
        group = sample_group_service.create_group(GroupCreate(name="Bumblebees"), sample_user)

        settings = (
            db_session.query(GroupSettings).filter(GroupSettings.group_id == group.id).first()
        )
        assert settings is not None


class TestGroupServiceCreateAtomicity:
    """create_group must be all-or-nothing.

    It used to span four commits, and with the NullPool engine every commit closes
    the connection — so a blip between them left a durable group with no owner
    (undeletable, and its name blocks any retry) or with no settings.
    """

    def test_create_group_commits_once(self, sample_group_service, sample_user):
        """The whole creation is a single transaction, not a chain of four."""
        with patch.object(
            sample_group_service.db, "commit", wraps=sample_group_service.db.commit
        ) as commit:
            sample_group_service.create_group(GroupCreate(name="Bumblebees"), sample_user)

        assert commit.call_count == 1

    @pytest.mark.parametrize("failing_step", ["add_user", "set_user_role"])
    def test_create_group_rolls_back_on_mid_sequence_failure(
        self, sample_group_service, sample_user, db_session, failing_step
    ):
        """A failure after the group row is written takes the group with it."""
        with (
            patch.object(
                sample_group_service,
                failing_step,
                side_effect=OperationalError("x", {}, Exception()),
            ),
            patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback,
        ):
            with pytest.raises(OperationalError):
                sample_group_service.create_group(GroupCreate(name="Doomed"), sample_user)

        rollback.assert_called()
        assert not any(isinstance(obj, Group) for obj in db_session.new)
        assert db_session.query(Group).filter(Group.name == "Doomed").first() is None

    def test_create_group_rolls_back_when_settings_insert_fails(
        self, sample_group_service, sample_user, db_session
    ):
        """A failure on the final settings insert must not strand an ownerless group."""
        real_add = db_session.add

        def _add(obj):
            if isinstance(obj, GroupSettings):
                raise OperationalError("x", {}, Exception())
            return real_add(obj)

        with (
            patch.object(db_session, "add", side_effect=_add),
            patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback,
        ):
            with pytest.raises(OperationalError):
                sample_group_service.create_group(GroupCreate(name="Doomed"), sample_user)

        rollback.assert_called()
        assert db_session.query(Group).filter(Group.name == "Doomed").first() is None

    def test_create_group_name_free_again_after_failure(self, sample_group_service, db_session):
        """Nothing survives the failure, so the name can still be claimed afterwards.

        Under the old four-commit flow the group row was already durable when the
        next step blew up, so every retry 409'd on a name nobody could use or delete.
        """
        doomed_user = User(email="doomed@test.com", username="doomed_user", password_hash="x")
        db_session.add(doomed_user)
        db_session.commit()

        with patch.object(
            sample_group_service, "add_user", side_effect=OperationalError("x", {}, Exception())
        ):
            with pytest.raises(OperationalError):
                sample_group_service.create_group(GroupCreate(name="Doomed"), doomed_user)

        # create_group's rollback unwinds this session's outer transaction too, so
        # the actor has to be re-created before retrying.
        retry_user = User(email="retry@test.com", username="retry_user", password_hash="x")
        db_session.add(retry_user)
        db_session.commit()

        group = sample_group_service.create_group(GroupCreate(name="Doomed"), retry_user)

        assert group.id is not None
        assert sample_group_service.get_user_role(retry_user.id, group.id) == GroupRole.Owner
        assert group.settings is not None


class TestGroupServiceAddUser:
    def test_add_user_successful(self, sample_group_service, sample_group, user_factory):
        """Test that adding a new user to a group is successful"""
        new_user = user_factory(email="another@test.com", username="another_user")
        assert new_user not in sample_group.members
        assert sample_group not in new_user.groups
        assert sample_group_service.get_group_join_date(new_user.id, sample_group.id) is None

        sample_group_service.add_user(sample_group.id, new_user.id)
        assert new_user in sample_group.members
        assert sample_group in new_user.groups
        assert sample_group_service.get_group_join_date(new_user.id, sample_group.id) is not None

    def test_add_duplicate_user(self, sample_group_service, sample_group, user_factory):
        """Test that adding a user multiple times does not result in error or change to group addition metadata."""
        new_user = user_factory(email="another@test.com", username="another_user")
        assert new_user not in sample_group.members
        assert sample_group not in new_user.groups
        assert sample_group_service.get_group_join_date(new_user.id, sample_group.id) is None

        sample_group_service.add_user(sample_group.id, new_user.id)
        assert new_user in sample_group.members
        assert sample_group in new_user.groups
        user_join_date = sample_group_service.get_group_join_date(new_user.id, sample_group.id)
        assert user_join_date is not None

        # Add the same user again; confirm that join date is retained.
        sample_group_service.add_user(sample_group.id, new_user.id)
        assert new_user in sample_group.members
        assert sample_group in new_user.groups
        assert user_join_date == sample_group_service.get_group_join_date(
            new_user.id, sample_group.id
        )

    def test_add_user_twice_leaves_exactly_one_membership_row(
        self, sample_group_service, sample_group, user_factory, db_session
    ):
        """A repeated join must not create a second membership row.

        The older duplicate test above asserts through get_group_join_date, which
        calls .scalar() and so happily reports the first of two rows. This one
        counts the rows, which is the only assertion that can actually see the
        duplicate that used to be possible here.
        """
        new_user = user_factory(email="another@test.com", username="another_user")

        sample_group_service.add_user(sample_group.id, new_user.id)
        sample_group_service.add_user(sample_group.id, new_user.id)

        count = db_session.execute(
            select(func.count())
            .select_from(group_members)
            .where(
                group_members.c.group_id == sample_group.id,
                group_members.c.user_id == new_user.id,
            )
        ).scalar_one()
        assert count == 1

    def test_duplicate_membership_row_is_rejected_by_the_database(
        self, sample_group_service, sample_group, user_factory, db_session
    ):
        """The unique constraint exists and bites.

        Before uq_group_members_group_user, this insert succeeded and add_user's
        ``except IntegrityError`` branch was unreachable dead code.
        """
        new_user = user_factory(email="another@test.com", username="another_user")
        sample_group_service.add_user(sample_group.id, new_user.id)

        with pytest.raises(IntegrityError):
            with db_session.begin_nested():
                db_session.execute(
                    group_members.insert().values(
                        group_id=sample_group.id,
                        user_id=new_user.id,
                        role=GroupRole.Member.value,
                    )
                )

    def test_add_user_racing_past_the_membership_check_raises_409(
        self, sample_group_service, sample_group, user_factory, db_session
    ):
        """Two concurrent joins: the loser gets a 409, not a duplicate row.

        add_user is a check-then-act, so a second caller can pass
        is_user_in_group before the first commits. Patching that check to False
        reproduces exactly that interleaving. The database now stops the second
        insert, and add_user's previously dead IntegrityError handler turns it
        into a 409 rather than a 500.
        """
        new_user = user_factory(email="another@test.com", username="another_user")
        sample_group_service.add_user(sample_group.id, new_user.id)

        with patch.object(sample_group_service, "is_user_in_group", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                sample_group_service.add_user(sample_group.id, new_user.id)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT


class TestGroupServiceDelete:
    def test_delete_group_successful(
        self, db_session, sample_group_service, sample_group, sample_user
    ):
        """Test that the group creator can delete the group."""
        # Confirm user is the owners of the group.
        group_id = sample_group.id
        assert sample_user in sample_group.members
        assert sample_user.id == sample_group.created_by
        assert len(sample_user.created_groups) != 0
        assert (
            sample_group_service.get_user_role(sample_user.id, sample_group.id) == GroupRole.Owner
        )

        sample_group_service.delete_group(sample_group.id, sample_user.id)

        assert db_session.query(Group).get(group_id) is None
        assert len(sample_user.created_groups) == 0

    @pytest.mark.parametrize(
        "user_role",
        [
            GroupRole.Member,
            GroupRole.Admin,
        ],
    )
    def test_delete_group_non_permissive(
        self, db_session, sample_group_service, sample_group, user_factory, set_user_role, user_role
    ):
        """Test that the group creator can delete the group."""
        # Add user to the group.
        group_id = sample_group.id
        regular_user = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, regular_user.id)
        set_user_role(user_id=regular_user.id, group_id=sample_group.id, role=user_role)

        assert regular_user in sample_group.members
        assert sample_group_service.get_user_role(regular_user.id, sample_group.id) == user_role

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.delete_group(sample_group.id, regular_user.id)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == f"Requires at least {GroupRole.Owner} role"
        assert db_session.query(Group).get(group_id) is not None
        assert sample_group is not None

    def test_user_removes_themselves(self, sample_group_service, sample_group, user_factory):
        """Users should be able to remove themselves from a group"""
        user = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, user.id)
        assert user in sample_group.members
        assert sample_group in user.groups

        sample_group_service.remove_user(sample_group.id, user.id, user.id)
        assert user not in sample_group.members
        assert sample_group not in user.groups

    def test_sole_owner_last_member_leaves_deletes_group(
        self, db_session, sample_group_service, sample_group, sample_user
    ):
        """When the sole owner is also the last member, leaving deletes the group."""
        group_id = sample_group.id
        sample_group_service.remove_user(sample_group.id, sample_user.id, sample_user.id)
        assert db_session.get(Group, group_id) is None

    def test_sole_owner_cannot_leave_with_other_members(
        self, sample_group_service, sample_group, sample_user, user_factory
    ):
        """The sole owner cannot leave while other members would be stranded without an owner."""
        other = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, other.id)

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.remove_user(sample_group.id, sample_user.id, sample_user.id)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert (
            exc_info.value.detail
            == "Cannot remove the only group owner -- nominate a replacement first"
        )

    def test_multi_owner_can_remove_themself(
        self, sample_group_service, sample_group, sample_user, user_factory, set_user_role
    ):
        """If there are multiple owners, one can remove themselves."""
        user = user_factory(email="presidente@test.com", username="president")
        sample_group_service.add_user(sample_group.id, user.id)
        set_user_role(user_id=user.id, group_id=sample_group.id, role=GroupRole.Owner)

        owner_ids = sample_group_service.get_users_with_role(sample_group.id, GroupRole.Owner)
        assert len(owner_ids) == 2
        assert sample_user.id in owner_ids
        assert user.id in owner_ids

        sample_group_service.remove_user(sample_group.id, sample_user.id, sample_user.id)

        assert sample_user not in sample_group.members
        assert sample_group not in sample_user.groups

        owner_ids = sample_group_service.get_users_with_role(sample_group.id, GroupRole.Owner)
        assert len(owner_ids) == 1
        assert sample_user.id not in owner_ids
        assert user.id in owner_ids

    def test_last_member_leaving_deletes_group(
        self, db_session, sample_group_service, sample_group, sample_user, user_factory, set_user_role
    ):
        """When the last remaining member leaves, the group is deleted."""
        second_owner = user_factory(email="second@test.com", username="second_owner")
        sample_group_service.add_user(sample_group.id, second_owner.id)
        set_user_role(user_id=second_owner.id, group_id=sample_group.id, role=GroupRole.Owner)

        group_id = sample_group.id
        sample_group_service.remove_user(sample_group.id, sample_user.id, sample_user.id)
        sample_group_service.remove_user(sample_group.id, second_owner.id, second_owner.id)

        assert db_session.get(Group, group_id) is None

    @pytest.mark.parametrize(
        "user_role",
        [
            GroupRole.Admin,
            GroupRole.Owner,
        ],
    )
    def test_user_removed_by_other_authorized(
        self, sample_group_service, sample_group, user_factory, user_role, set_user_role
    ):
        """Admins and owners should be able to remove other users"""
        user = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, user.id)
        set_user_role(user_id=user.id, group_id=sample_group.id, role=user_role)
        assert user in sample_group.members
        assert sample_group in user.groups

        other_user = user_factory(email="jill@test.com", username="jillybean")
        sample_group_service.add_user(sample_group.id, other_user.id)
        assert other_user in sample_group.members
        assert sample_group in other_user.groups

        sample_group_service.remove_user(sample_group.id, other_user.id, user.id)
        assert other_user not in sample_group.members
        assert sample_group not in other_user.groups

    def test_user_removed_by_other_unauthorized(
        self, sample_group_service, sample_group, user_factory
    ):
        """Members should not be able to remove other members"""
        user = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, user.id)
        assert user in sample_group.members
        assert sample_group in user.groups

        other_user = user_factory(email="jill@test.com", username="jillybean")
        sample_group_service.add_user(sample_group.id, other_user.id)
        assert other_user in sample_group.members
        assert sample_group in other_user.groups

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.remove_user(sample_group.id, other_user.id, user.id)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert (
            exc_info.value.detail
            == f"Requires at least {GroupRole.Admin} role"
        )


class TestGroupServiceRemoveUserPendingNominations:
    """Pending nominations by a departing member should be cleaned up."""

    def _add_nomination(self, db_session, group_id, album_id, user_id, *, selected=False):
        ga = GroupAlbum(
            group_id=group_id,
            album_id=album_id,
            added_by=user_id,
            selected_date=datetime.now(tz=timezone.utc) if selected else None,
        )
        db_session.add(ga)
        db_session.commit()
        db_session.refresh(ga)
        return ga

    def test_pending_nomination_removed_on_leave(
        self, db_session, sample_group_service, sample_group, sample_user, sample_album, user_factory
    ):
        """A departing member's pending nomination is deleted."""
        leaver = user_factory(email="leaver@test.com", username="leaver")
        sample_group_service.add_user(sample_group.id, leaver.id)
        ga_id = self._add_nomination(db_session, sample_group.id, sample_album.id, leaver.id).id

        sample_group_service.remove_user(sample_group.id, leaver.id, leaver.id)

        assert db_session.get(GroupAlbum, ga_id) is None

    def test_selected_nomination_retained_on_leave(
        self, db_session, sample_group_service, sample_group, sample_user, sample_album, user_factory
    ):
        """Already-selected nominations are not deleted when the nominator leaves."""
        leaver = user_factory(email="leaver@test.com", username="leaver")
        sample_group_service.add_user(sample_group.id, leaver.id)
        ga_id = self._add_nomination(db_session, sample_group.id, sample_album.id, leaver.id, selected=True).id

        sample_group_service.remove_user(sample_group.id, leaver.id, leaver.id)

        assert db_session.get(GroupAlbum, ga_id) is not None

    def test_co_nominated_album_survives_partial_departure(
        self, db_session, sample_group_service, sample_group, sample_user, sample_album, user_factory
    ):
        """When multiple members nominated the same album, only the leaver's row is removed."""
        leaver = user_factory(email="leaver@test.com", username="leaver")
        sample_group_service.add_user(sample_group.id, leaver.id)
        leaver_ga_id = self._add_nomination(db_session, sample_group.id, sample_album.id, leaver.id).id
        stayer_ga_id = self._add_nomination(db_session, sample_group.id, sample_album.id, sample_user.id).id

        sample_group_service.remove_user(sample_group.id, leaver.id, leaver.id)

        assert db_session.get(GroupAlbum, leaver_ga_id) is None
        assert db_session.get(GroupAlbum, stayer_ga_id) is not None


class TestGroupServiceGetters:
    @pytest.mark.parametrize(
        "group_name_case",
        [
            ("",),
            ("lower",),
            ("upper",),
            ("title",),
            ("random",),
        ],
    )
    def test_get_group_by_name_valid(self, sample_group_service, sample_group, group_name_case):
        """Ensure get group by name is case insensitive"""
        new_group_name = sample_group.name
        if group_name_case == "lower":
            new_group_name = new_group_name.lower()
        elif group_name_case == "upper":
            new_group_name = new_group_name.upper()
        elif group_name_case == "title":
            new_group_name = new_group_name.title()
        elif group_name_case == "random":
            new_group_name = "".join(
                [x.upper() if random.random() > 0.5 else x.lower() for x in new_group_name]
            )
        group = sample_group_service.get_group_by_name(new_group_name)
        assert group is not None
        assert group == sample_group

    def test_get_group_by_name_invalid(self, sample_group_service, sample_group):
        """Ensure get group by name returns None if none found"""
        assert sample_group_service.get_group_by_name("not_a_valid_group") is None

    def test_get_group_join_date_valid(self, sample_group_service, sample_group, sample_user):
        """Ensure get group join date returns consistent datetime when user is in the group"""
        join_date = sample_group_service.get_group_join_date(sample_user.id, sample_group.id)
        assert join_date is not None

    def test_get_group_join_date_invalid(self, sample_group_service, sample_group, sample_user):
        """Ensure get group join date returns None when user is not in the group"""
        test_user_id = 42
        assert not sample_group_service.is_user_in_group(test_user_id, sample_group.id)
        assert sample_group_service.get_group_join_date(test_user_id, sample_group.id) is None


class TestGroupServiceMutators:

    @pytest.mark.parametrize(
        "user_role",
        [
            GroupRole.Member,
            GroupRole.Admin,
            GroupRole.Owner,
        ],
    )
    def test_set_user_role_permissive(
        self, sample_group_service, sample_group, set_user_role, user_factory, user_role
    ):
        """Test that only users with elevated permissions may modify other's roles."""
        user_modifying = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, user_modifying.id)
        user_to_set = user_factory(email="jill@test.com", username="jill")
        sample_group_service.add_user(sample_group.id, user_to_set.id)

        # Update modifying user
        set_user_role(user_id=user_modifying.id, group_id=sample_group.id, role=user_role)

        for role in GroupRole:
            user_role_before = sample_group_service.get_user_role(user_to_set.id, sample_group.id)
            if user_role > role:
                with pytest.raises(HTTPException) as exc_info:
                    sample_group_service.set_user_role(
                        user_to_set.id, user_modifying.id, sample_group.id, role=role
                    )
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert (
                    exc_info.value.detail
                    == f"Requires at least {role} role"
                )
                assert (
                    sample_group_service.get_user_role(user_to_set.id, sample_group.id)
                    == user_role_before
                )
            else:
                sample_group_service.set_user_role(
                    user_to_set.id, user_modifying.id, sample_group.id, role=role
                )
                assert sample_group_service.get_user_role(user_to_set.id, sample_group.id) == role

    @pytest.mark.parametrize(
        "user_role",
        [
            GroupRole.Member,
            GroupRole.Admin,
            GroupRole.Owner,
        ],
    )
    def test_set_user_role_force(
        self, sample_group_service, sample_group, set_user_role, user_factory, user_role
    ):
        """Test that if force is set that any user can set any other user's role."""
        user_modifying = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, user_modifying.id)
        user_to_set = user_factory(email="jill@test.com", username="jill")
        sample_group_service.add_user(sample_group.id, user_to_set.id)

        # Update modifying user
        set_user_role(user_id=user_modifying.id, group_id=sample_group.id, role=user_role)

        for role in GroupRole:
            sample_group_service.set_user_role(
                user_to_set.id, user_modifying.id, sample_group.id, role=role, force=True
            )
            assert sample_group_service.get_user_role(user_to_set.id, sample_group.id) == role

    def test_set_user_role_setter_not_in_group(
        self, sample_group_service, sample_group, user_factory
    ):
        """Test that if the setter is not in the group an exception is thrown"""
        user_modifying = user_factory(email="joe@test.com", username="joe_schmo")
        user_to_set = user_factory(email="jill@test.com", username="jill")
        sample_group_service.add_user(sample_group.id, user_to_set.id)

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.set_user_role(
                user_to_set.id, user_modifying.id, sample_group.id, role=GroupRole.Member
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "You must be a member of this group"

    def test_set_user_role_user_not_in_group(
        self, sample_group_service, sample_group, sample_user, user_factory
    ):
        """Test that if the target user is not in the group an exception is thrown"""
        user_to_set = user_factory(email="jill@test.com", username="jill")

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.set_user_role(
                user_to_set.id, sample_user.id, sample_group.id, role=GroupRole.Member
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "You must be a member of this group"

    @pytest.mark.parametrize("new_role", [GroupRole.Admin, GroupRole.Member])
    def test_sole_owner_cannot_demote_themselves(
        self, sample_group_service, sample_group, sample_user, new_role
    ):
        """The sole owner cannot change their own role — they must promote another member first."""
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.set_user_role(
                sample_user.id, sample_user.id, sample_group.id, role=new_role
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert (
            exc_info.value.detail
            == "Cannot demote the only group owner -- promote another member first"
        )
        assert sample_group_service.get_user_role(sample_user.id, sample_group.id) == GroupRole.Owner

    @pytest.mark.parametrize("new_role", [GroupRole.Admin, GroupRole.Member])
    def test_sole_owner_cannot_be_demoted_by_another_owner(
        self, sample_group_service, sample_group, sample_user, user_factory, set_user_role, new_role
    ):
        """Another owner cannot demote the sole remaining owner."""
        second_owner = user_factory(email="second@test.com", username="second_owner")
        sample_group_service.add_user(sample_group.id, second_owner.id)
        set_user_role(user_id=second_owner.id, group_id=sample_group.id, role=GroupRole.Owner)

        # Demote second_owner so sample_user is the only owner again
        sample_group_service.set_user_role(
            second_owner.id, sample_user.id, sample_group.id, role=GroupRole.Admin
        )

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.set_user_role(
                sample_user.id, second_owner.id, sample_group.id, role=new_role
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert (
            exc_info.value.detail
            == "Cannot demote the only group owner -- promote another member first"
        )

    @pytest.mark.parametrize("new_role", [GroupRole.Admin, GroupRole.Member])
    def test_owner_can_demote_themselves_when_another_owner_exists(
        self, sample_group_service, sample_group, sample_user, user_factory, set_user_role, new_role
    ):
        """An owner can change their own role once another owner has been promoted."""
        second_owner = user_factory(email="second@test.com", username="second_owner")
        sample_group_service.add_user(sample_group.id, second_owner.id)
        set_user_role(user_id=second_owner.id, group_id=sample_group.id, role=GroupRole.Owner)

        sample_group_service.set_user_role(
            sample_user.id, sample_user.id, sample_group.id, role=new_role
        )
        assert sample_group_service.get_user_role(sample_user.id, sample_group.id) == new_role

    @pytest.mark.parametrize(
        "user_role",
        [
            GroupRole.Admin,
            GroupRole.Owner,
        ],
    )
    def test_update_group_settings_permissive(
        self, sample_group, sample_group_service, user_factory, set_user_role, user_role
    ):
        user_modifying = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, user_modifying.id)
        set_user_role(user_id=user_modifying.id, group_id=sample_group.id, role=user_role)

        new_name = "NewGroupName"
        new_visibility = not sample_group.is_public

        request = GroupModifyRequest(name=new_name, is_public=new_visibility)
        sample_group_service.update_group_settings(sample_group.id, user_modifying.id, request)
        assert sample_group.name == new_name
        assert sample_group.name_uniform == new_name.lower()
        assert sample_group.is_public == new_visibility

    @pytest.mark.parametrize(
        "user_role",
        [GroupRole.Member],
    )
    def test_update_group_settings_nonpermissive(
        self, sample_group, sample_group_service, user_factory, set_user_role, user_role
    ):
        user_modifying = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, user_modifying.id)
        set_user_role(user_id=user_modifying.id, group_id=sample_group.id, role=user_role)

        new_name = "NewGroupName"
        new_visibility = not sample_group.is_public

        request = GroupModifyRequest(name=new_name, is_public=new_visibility)
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(sample_group.id, user_modifying.id, request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == f"Requires at least {GroupRole.Admin} role"

    def test_update_group_settings_same_name_allowed(
        self, sample_group, sample_group_service, sample_user
    ):
        """Saving a group with its current name (e.g. when only updating policy settings) must not raise."""
        request = GroupModifyRequest(name=sample_group.name, is_public=sample_group.is_public)
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group.name == sample_group.name

    def test_update_priority_pick_threshold(
        self, sample_group, sample_group_service, sample_user
    ):
        """priority_pick_threshold round-trips; an explicit null disables the feature."""
        request = GroupModifyRequest(settings=GroupSettingsUpdate(priority_pick_threshold=10))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group_service.get_group_settings(sample_group.id).priority_pick_threshold == 10

        # Absent field leaves it unchanged (model_fields_set gate).
        sample_group_service.update_group_settings(
            sample_group.id, sample_user.id,
            GroupModifyRequest(settings=GroupSettingsUpdate(daily_album_count=2)),
        )
        assert sample_group_service.get_group_settings(sample_group.id).priority_pick_threshold == 10

        # Explicit null disables.
        sample_group_service.update_group_settings(
            sample_group.id, sample_user.id,
            GroupModifyRequest(settings=GroupSettingsUpdate(priority_pick_threshold=None)),
        )
        assert sample_group_service.get_group_settings(sample_group.id).priority_pick_threshold is None

    def test_update_group_settings_name_conflict(
        self, sample_group, sample_group_service, sample_user, group_factory
    ):
        new_name = "NewGroupName"
        _ = group_factory(name=new_name)

        # test identical name
        request = GroupModifyRequest(name=new_name)
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "Group name already registered"

        # test case insensitivity
        request = GroupModifyRequest(name=new_name.upper())
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT


class TestGroupServiceSettings:
    def test_create_group_initializes_settings(self, sample_group_service, sample_user):
        """Creating a group initializes settings with defaults."""
        group = sample_group_service.create_group(GroupCreate(name="SettingsTest"), sample_user)
        assert group.settings is not None
        assert group.settings.min_role_to_add_members == "admin"
        assert group.settings.daily_album_count == 1

    def test_update_settings_daily_count(self, sample_group, sample_group_service, sample_user):
        """Owner can update daily_album_count."""
        request = GroupModifyRequest(settings=GroupSettingsUpdate(daily_album_count=5))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group.settings.daily_album_count == 5

    def test_update_settings_min_role(self, sample_group, sample_group_service, sample_user):
        """Owner can update min_role_to_add_members."""
        request = GroupModifyRequest(settings=GroupSettingsUpdate(min_role_to_add_members="member"))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group.settings.min_role_to_add_members == "member"

    def test_update_settings_daily_count_exceeds_max(self):
        """daily_album_count above 10 is rejected at schema validation."""
        with pytest.raises(ValidationError):
            GroupModifyRequest(settings=GroupSettingsUpdate(daily_album_count=11))

    def test_update_settings_daily_count_below_min(self):
        """daily_album_count below 1 is rejected at schema validation."""
        with pytest.raises(ValidationError):
            GroupModifyRequest(settings=GroupSettingsUpdate(daily_album_count=0))

    def test_update_settings_invalid_role(self):
        """Invalid role value is rejected at schema validation."""
        with pytest.raises(ValidationError):
            GroupModifyRequest(settings=GroupSettingsUpdate(min_role_to_add_members="superadmin"))

    def test_update_settings_member_cannot_modify(
        self, sample_group, sample_group_service, user_factory, set_user_role
    ):
        """Regular members cannot update group settings."""
        member = user_factory(email="joe@test.com", username="joe_schmo")
        sample_group_service.add_user(sample_group.id, member.id)
        set_user_role(user_id=member.id, group_id=sample_group.id, role=GroupRole.Member)

        request = GroupModifyRequest(settings=GroupSettingsUpdate(daily_album_count=3))
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(sample_group.id, member.id, request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_update_settings_allow_guessing(self, sample_group, sample_group_service, sample_user):
        """Owner can toggle allow_guessing."""
        request = GroupModifyRequest(settings=GroupSettingsUpdate(allow_guessing=False))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group.settings.allow_guessing is False

        request2 = GroupModifyRequest(settings=GroupSettingsUpdate(allow_guessing=True))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request2)
        assert sample_group.settings.allow_guessing is True

    def test_update_settings_min_role_to_nominate(self, sample_group, sample_group_service, sample_user):
        """Owner can update min_role_to_nominate."""
        request = GroupModifyRequest(settings=GroupSettingsUpdate(min_role_to_nominate="admin"))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group.settings.min_role_to_nominate == "admin"

    def test_create_group_initializes_dealer_defaults(self, sample_group_service, sample_user):
        """New groups default to dealer mode off with 1 roll per day."""
        group = sample_group_service.create_group(GroupCreate(name="DealerDefaults"), sample_user)
        assert group.settings.dealer_mode is False
        assert group.settings.dealer_rolls_per_day == 1

    def test_update_settings_dealer_mode_toggle(self, sample_group, sample_group_service, sample_user):
        """Owner can toggle dealer_mode on and off."""
        request = GroupModifyRequest(settings=GroupSettingsUpdate(dealer_mode=True))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group.settings.dealer_mode is True

        request2 = GroupModifyRequest(settings=GroupSettingsUpdate(dealer_mode=False))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request2)
        assert sample_group.settings.dealer_mode is False

    def test_update_settings_dealer_rolls_per_day(self, sample_group, sample_group_service, sample_user):
        """Owner can update dealer_rolls_per_day."""
        request = GroupModifyRequest(settings=GroupSettingsUpdate(dealer_rolls_per_day=3))
        sample_group_service.update_group_settings(sample_group.id, sample_user.id, request)
        assert sample_group.settings.dealer_rolls_per_day == 3

    def test_update_settings_dealer_rolls_exceeds_max(self):
        """dealer_rolls_per_day above 10 is rejected at schema validation."""
        with pytest.raises(ValidationError):
            GroupModifyRequest(settings=GroupSettingsUpdate(dealer_rolls_per_day=11))

    def test_update_settings_dealer_rolls_below_min(self):
        """dealer_rolls_per_day below 1 is rejected at schema validation."""
        with pytest.raises(ValidationError):
            GroupModifyRequest(settings=GroupSettingsUpdate(dealer_rolls_per_day=0))


class TestGlobalGroup:
    def test_delete_global_group_forbidden(self, sample_group_service, global_group, sample_user):
        """The global group cannot be deleted by anyone."""
        sample_group_service.add_user(global_group.id, sample_user.id)

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.delete_group(global_group.id, sample_user.id)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "global group" in exc_info.value.detail

    def test_global_group_not_deleted_when_empty(
        self, db_session, sample_group_service, global_group, sample_user
    ):
        """Removing the last member of the global group must not delete it."""
        sample_group_service.add_user(global_group.id, sample_user.id)
        group_id = global_group.id

        sample_group_service.remove_user(global_group.id, sample_user.id, sample_user.id)

        assert db_session.get(Group, group_id) is not None

    def test_update_global_group_settings_forbidden(
        self, sample_group_service, global_group, sample_user
    ):
        """Settings changes on the global group are blocked for non-admins."""
        sample_group_service.add_user(global_group.id, sample_user.id)
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(
                global_group.id, sample_user.id, GroupModifyRequest(name="renamed")
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_update_global_group_dealer_mode_by_site_admin(
        self, db_session, sample_group_service, global_group, user_factory
    ):
        """Site admins may toggle dealer mode on the global group."""
        admin = user_factory(email="admin@test.com", username="site_admin")
        admin.is_admin = True
        db_session.commit()

        sample_group_service.update_group_settings(
            global_group.id,
            admin.id,
            GroupModifyRequest(
                settings=GroupSettingsUpdate(dealer_mode=True, dealer_rolls_per_day=3)
            ),
        )

        db_session.refresh(global_group.settings)
        assert global_group.settings.dealer_mode is True
        assert global_group.settings.dealer_rolls_per_day == 3

    def test_update_global_group_non_dealer_fields_forbidden_for_site_admin(
        self, db_session, sample_group_service, global_group, user_factory
    ):
        """Even site admins cannot rename or otherwise reconfigure the global group."""
        admin = user_factory(email="admin2@test.com", username="site_admin2")
        admin.is_admin = True
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(
                global_group.id, admin.id, GroupModifyRequest(name="renamed")
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(
                global_group.id,
                admin.id,
                GroupModifyRequest(settings=GroupSettingsUpdate(chaos_mode=True)),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_update_global_group_dealer_mode_forbidden_for_non_admin(
        self, sample_group_service, global_group, sample_user
    ):
        """A non-site-admin cannot toggle dealer mode on the global group either."""
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.update_group_settings(
                global_group.id,
                sample_user.id,
                GroupModifyRequest(settings=GroupSettingsUpdate(dealer_mode=True)),
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_get_global_group(self, sample_group_service, global_group):
        """get_global_group returns the seeded global group."""
        result = sample_group_service.get_global_group()
        assert result is not None
        assert result.id == global_group.id
        assert result.is_global


class TestRequirePublicOrMember:
    """Read-access guard for the landing-page/anonymous-browsing flows."""

    def test_anonymous_allowed_on_global_group(self, sample_group_service, global_group):
        sample_group_service.require_public_or_member(global_group, None)

    def test_anonymous_allowed_on_bot_group(
        self, db_session, sample_group_service, sample_group, user_factory
    ):
        bot_user = user_factory(email="bot@test.com", username="bot_user")
        db_session.add(BotSource(name="Test Bot", bot_user_id=bot_user.id, bot_group_id=sample_group.id))
        db_session.commit()
        db_session.refresh(sample_group)

        sample_group_service.require_public_or_member(sample_group, None)

    def test_anonymous_forbidden_on_regular_public_group(self, sample_group_service, sample_group):
        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.require_public_or_member(sample_group, None)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_non_member_forbidden_on_private_group(
        self, db_session, sample_group_service, sample_group, user_factory
    ):
        sample_group.is_public = False
        db_session.commit()
        outsider = user_factory(email="outsider@test.com", username="outsider")

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.require_public_or_member(sample_group, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated_non_member_allowed_on_public_group(
        self, sample_group_service, sample_group, user_factory
    ):
        outsider = user_factory(email="outsider@test.com", username="outsider")
        sample_group_service.require_public_or_member(sample_group, outsider)


class TestGroupServiceSearch:
    def test_search_by_username_includes_private_groups(
        self, sample_group_service, sample_user, group_factory
    ):
        """Private groups appear when searching by the member's username."""
        private_group = group_factory(name="Secret-Spins", is_public=False)
        results = sample_group_service.search_groups(username=sample_user.username)
        assert any(g.id == private_group.id for g in results)

    def test_search_without_username_excludes_private_groups(
        self, sample_group_service, sample_user, group_factory
    ):
        """Private groups must not appear in generic (no-username) searches."""
        private_group = group_factory(name="Hidden-Spins", is_public=False)
        results = sample_group_service.search_groups(query="hidden")
        assert not any(g.id == private_group.id for g in results)

    def test_search_without_username_returns_public_groups(
        self, sample_group_service, sample_user, group_factory
    ):
        public_group = group_factory(name="Open-Spins", is_public=True)
        results = sample_group_service.search_groups(query="open")
        assert any(g.id == public_group.id for g in results)

    def test_search_orders_newest_first(
        self, sample_group_service, sample_user, group_factory
    ):
        """Results come back newest-first so limit truncation is deterministic."""
        groups = [group_factory(name=f"Order-Test-{i}") for i in range(3)]
        results = sample_group_service.search_groups(username=sample_user.username)
        result_ids = [g.id for g in results]
        # The most recently created group must be first
        assert result_ids[0] == groups[-1].id
        assert result_ids == sorted(result_ids, reverse=True)

    def test_search_by_username_beyond_default_limit_keeps_newest(
        self, sample_group_service, sample_user, group_factory
    ):
        """A member of >10 groups still sees their newest group within the default
        limit, and a raised limit returns all memberships (regression: 'my groups'
        silently dropped new groups once a user exceeded 10)."""
        groups = [group_factory(name=f"Many-Groups-{i}") for i in range(12)]

        default_results = sample_group_service.search_groups(username=sample_user.username)
        assert len(default_results) == 10
        assert default_results[0].id == groups[-1].id

        all_results = sample_group_service.search_groups(
            username=sample_user.username, limit=100
        )
        assert {g.id for g in groups} <= {g.id for g in all_results}


class TestGroupJoinNotifications:
    def test_existing_members_notified_when_user_joins(
        self, db_session, sample_group_service, sample_group, sample_user, user_factory
    ):
        new_user = user_factory(email="new@test.com", username="newmember")
        sample_group_service.add_user(sample_group.id, new_user.id)

        ns = NotificationService(db_session)
        unread = ns.get_unread(sample_user)
        assert len(unread) == 1
        assert unread[0].type == NotificationType.new_member_joined
        assert unread[0].group_id == sample_group.id
        assert "newmember" in unread[0].message

    def test_no_notification_when_first_member_added(
        self, db_session, sample_group_service, sample_user
    ):
        from app.schemas.group import GroupCreate
        group = sample_group_service.create_group(GroupCreate(name="fresh-group"), sample_user)

        ns = NotificationService(db_session)
        assert ns.get_unread(sample_user) == []

    def test_no_notification_for_global_group_join(
        self, db_session, sample_group_service, global_group, sample_user, user_factory
    ):
        global_group.members.append(sample_user)
        db_session.commit()
        new_user = user_factory(email="new@test.com", username="globaljoiner")

        sample_group_service.add_user(global_group.id, new_user.id)

        ns = NotificationService(db_session)
        assert ns.get_unread(sample_user) == []

    def test_joiner_does_not_receive_their_own_join_notification(
        self, db_session, sample_group_service, sample_group, sample_user, user_factory
    ):
        new_user = user_factory(email="new@test.com", username="newmember")
        sample_group_service.add_user(sample_group.id, new_user.id)

        ns = NotificationService(db_session)
        assert ns.get_unread(new_user) == []


# ==================== QUERY-COUNT GUARDS ====================
#
# app.database uses a NullPool against a serverless Postgres, so a statement is
# a network round trip and the statement count is what a call costs. No model
# declares ``lazy=``, so any relationship touched inside a loop is silently an
# N+1 that no correctness test would notice. These assert the count does not
# grow with the data.


@contextmanager
def count_statements(db_session):
    """Collect the SQL the session emits inside the block, minus savepoint noise."""
    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany):
        head = statement.lstrip().upper()
        if head.startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK TO SAVEPOINT")):
            return
        statements.append(statement)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", record)


def _add_albums(db_session, group, user, count, *, offset=0, reviewed=True):
    """Nominate ``count`` albums into ``group``, optionally each with a review."""
    for i in range(count):
        album = Album(
            spotify_album_id=f"stats-{offset + i}",
            title=f"Album {offset + i}",
            artist=f"Artist {offset + i}",
            release_date=f"{1970 + (offset + i) % 50}-01-01",
        )
        db_session.add(album)
        db_session.flush()
        db_session.add(
            GroupAlbum(
                group_id=group.id,
                album_id=album.id,
                added_by=user.id,
                selected_date=datetime.now(timezone.utc),
            )
        )
        if reviewed:
            db_session.add(Review(user_id=user.id, album_id=album.id, rating=7.0))
    db_session.commit()


class TestGroupServiceQueryCounts:
    def test_group_stats_does_not_scale_with_album_count(
        self, sample_group_service, sample_group, sample_user, db_session
    ):
        """``albums_reviewed`` reads the ``status`` hybrid, whose Python branch
        walks ``albums.reviews`` — a relationship the method's eager load does
        not cover. Counting it in Python was one query per album.
        """
        _add_albums(db_session, sample_group, sample_user, 3)
        group_id = sample_group.id
        with count_statements(db_session) as small:
            small_stats = sample_group_service.get_group_stats(group_id)

        _add_albums(db_session, sample_group, sample_user, 27, offset=100)
        with count_statements(db_session) as large:
            large_stats = sample_group_service.get_group_stats(group_id)

        assert small_stats["albums_reviewed"] == 3
        assert large_stats["albums_reviewed"] == 30
        assert len(large) == len(small), (small, large)

    def test_set_user_role_reads_group_members_once(
        self, sample_group_service, sample_group, sample_user, group_member, db_session
    ):
        """Membership and role, for both the setter and the target, are one read."""
        group_id, setter_id, target_id = sample_group.id, sample_user.id, group_member.id

        with count_statements(db_session) as statements:
            sample_group_service.set_user_role(
                target_id, setter_id, group_id, GroupRole.Admin
            )

        reads = [
            s
            for s in statements
            if "group_members" in s and s.lstrip().upper().startswith("SELECT")
        ]
        assert len(reads) == 1, reads
        assert sample_group_service.get_user_role(target_id, group_id) == GroupRole.Admin

    def test_add_user_fans_out_notifications_in_one_insert(
        self, sample_group_service, sample_group, db_session, user_factory
    ):
        """``NotificationService.create`` commits per recipient; the fan-out must
        not pay three round trips per existing member."""
        for i in range(5):
            member = user_factory(email=f"fan{i}@test.com", username=f"fanmember{i}")
            db_session.execute(
                group_members.insert().values(
                    group_id=sample_group.id, user_id=member.id, role=GroupRole.Member.value
                )
            )
        db_session.commit()
        joiner = user_factory(email="joiner@test.com", username="joiner")
        group_id, joiner_id = sample_group.id, joiner.id

        with count_statements(db_session) as statements:
            sample_group_service.add_user(group_id, joiner_id)

        inserts = [
            s for s in statements if s.lstrip().upper().startswith("INSERT INTO NOTIFICATIONS")
        ]
        assert len(inserts) == 1, inserts
        ns = NotificationService(db_session)
        # All six prior members (owner + five) were notified.
        assert sum(len(ns.get_unread(u)) for u in db_session.query(User).all()) == 6

    def test_search_groups_eager_loads_settings_and_bot_sources(
        self, sample_group_service, sample_user, db_session
    ):
        """The search response renders both per result, so they must not be
        lazy-loaded one group at a time."""

        def make(n, offset):
            for i in range(n):
                group = Group(name=f"searchable-{offset + i}", is_public=True)
                db_session.add(group)
                db_session.flush()
                db_session.add(GroupSettings(group_id=group.id))
            db_session.commit()

        def render(limit):
            with count_statements(db_session) as statements:
                for g in sample_group_service.search_groups(query="searchable", limit=limit):
                    _ = bool(g.bot_sources), g.settings
            return statements

        make(3, 0)
        small = render(50)
        make(27, 100)
        large = render(50)

        assert len(large) == len(small), (small, large)
        assert len(small) <= 3
