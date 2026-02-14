import random

import pytest
from app.models.group import Group, GroupRole
from app.schemas.group import GroupCreate, GroupModifyRequest
from fastapi import HTTPException, status


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
        assert exc_info.value.detail == "Only owners may delete the group"
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

    def test_sole_owner_cannot_remove_themself(
        self, sample_group_service, sample_group, sample_user
    ):
        """If there is only one owner, they cannot remove themselves"""
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
        """If there is are multiple owners, they can remove themselves"""
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
            == "Only group admins, owners, or member themselves can remove members."
        )


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
            if role > user_role:
                with pytest.raises(HTTPException) as exc_info:
                    sample_group_service.set_user_role(
                        user_to_set.id, user_modifying.id, sample_group.id, role=role
                    )
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert (
                    exc_info.value.detail
                    == "Users are not permitted to set roles greater than their own"
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

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Setter not found in group"

    def test_set_user_role_user_not_in_group(
        self, sample_group_service, sample_group, sample_user, user_factory
    ):
        """Test that if the target user is not in the group an exception is thrown"""
        user_to_set = user_factory(email="jill@test.com", username="jill")

        with pytest.raises(HTTPException) as exc_info:
            sample_group_service.set_user_role(
                user_to_set.id, sample_user.id, sample_group.id, role=GroupRole.Member
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "User not found in group"

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
        assert exc_info.value.detail == "Only admins and owners may modify group settings"

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
        assert exc_info.value.detail == "Group name already registered"
