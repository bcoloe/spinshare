import random
from datetime import datetime, timezone

import pytest
from app.models import GroupAlbum
from app.models.group import Group, GroupRole
from app.schemas.group import GroupCreate, GroupModifyRequest, GroupSettingsUpdate
from fastapi import HTTPException, status
from pydantic import ValidationError


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
