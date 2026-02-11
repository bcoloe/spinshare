import random

import pytest
from app.schemas.group import GroupCreate
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
        assert sample_user in group.members

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
