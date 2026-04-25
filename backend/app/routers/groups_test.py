# backend/app/routers/groups_test.py
#
# Router tests: verify HTTP status codes, request/response shapes, and auth
# enforcement. The GroupService is fully mocked — business logic is tested
# in group_service_test.py.

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from app.models.group import GroupRole
from app.routers.conftest import make_mock_group, make_mock_settings, make_mock_user
from fastapi import status

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestGroupCreate:
    def test_create_group_success(self, client, mock_group_service):
        mock_group_service.create_group.return_value = make_mock_group(name="Bumblebees")

        resp = client.post("/groups/", json={"name": "Bumblebees"})

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["name"] == "Bumblebees"
        mock_group_service.create_group.assert_called_once()

    def test_create_group_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/", json={"name": "Bumblebees"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_group_conflict(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.create_group.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Group name already registered"
        )
        resp = client.post("/groups/", json={"name": "Bumblebees"})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_create_group_invalid_name(self, client):
        resp = client.post("/groups/", json={"name": "bad name!"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_private_group(self, client, mock_group_service):
        mock_group_service.create_group.return_value = make_mock_group(
            name="SecretClub", is_public=False
        )
        resp = client.post("/groups/", json={"name": "SecretClub", "is_public": False})
        assert resp.status_code == status.HTTP_201_CREATED


class TestGroupGet:
    def test_get_group_by_id_public(self, client, mock_group_service, mock_user):
        group = make_mock_group()
        mock_group_service.get_group_by_id.return_value = group
        mock_group_service.is_user_in_group.return_value = False
        mock_group_service.get_user_role.return_value = None

        resp = client.get("/groups/1")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["id"] == 1
        assert "is_public" in data
        assert "member_count" in data

    def test_get_group_not_found(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.get_group_by_id.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
        resp = client.get("/groups/99999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_get_private_group_as_member(self, client, mock_group_service, mock_user):
        group = make_mock_group(is_public=False)
        mock_group_service.get_group_by_id.return_value = group
        mock_group_service.is_user_in_group.return_value = True
        mock_group_service.get_user_role.return_value = GroupRole.Member

        resp = client.get("/groups/1")
        assert resp.status_code == status.HTTP_200_OK

    def test_get_private_group_as_non_member(self, client, mock_group_service):
        group = make_mock_group(is_public=False)
        mock_group_service.get_group_by_id.return_value = group
        mock_group_service.is_user_in_group.return_value = False

        resp = client.get("/groups/1")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_get_group_by_name(self, client, mock_group_service):
        group = make_mock_group(name="Bumblebees")
        mock_group_service.get_group_by_name.return_value = group
        mock_group_service.is_user_in_group.return_value = True
        mock_group_service.get_user_role.return_value = GroupRole.Owner

        resp = client.get("/groups/name/Bumblebees")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "Bumblebees"

    def test_get_group_by_name_not_found(self, client, mock_group_service):
        mock_group_service.get_group_by_name.return_value = None
        resp = client.get("/groups/name/nonexistent")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestGroupUpdate:
    def test_update_group_success(self, client, mock_group_service):
        updated = make_mock_group(name="NewName")
        mock_group_service.get_group_by_id.return_value = updated
        mock_group_service.get_user_role.return_value = GroupRole.Owner

        resp = client.patch("/groups/1", json={"name": "NewName"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "NewName"
        mock_group_service.update_group_settings.assert_called_once()

    def test_update_group_forbidden(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.update_group_settings.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires at least admin role"
        )
        resp = client.patch("/groups/1", json={"name": "Hijacked"})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_update_group_name_conflict(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.update_group_settings.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Group name already registered"
        )
        resp = client.patch("/groups/1", json={"name": "TakenName"})
        assert resp.status_code == status.HTTP_409_CONFLICT


class TestGroupDelete:
    def test_delete_group_success(self, client, mock_group_service):
        resp = client.delete("/groups/1")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_group_service.delete_group.assert_called_once()

    def test_delete_group_forbidden(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.delete_group.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires at least owner role"
        )
        resp = client.delete("/groups/1")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestGroupJoin:
    def test_join_public_group(self, client, mock_group_service):
        group = make_mock_group(is_public=True)
        mock_group_service.get_group_by_id.return_value = group
        mock_group_service.get_group_join_date.return_value = _NOW

        resp = client.post("/groups/1/join")

        assert resp.status_code == status.HTTP_200_OK
        assert "joined_at" in resp.json()
        mock_group_service.add_user.assert_called_once()

    def test_join_private_group_forbidden(self, client, mock_group_service):
        group = make_mock_group(is_public=False)
        mock_group_service.get_group_by_id.return_value = group

        resp = client.post("/groups/1/join")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        mock_group_service.add_user.assert_not_called()


class TestGroupMembers:
    def test_list_members(self, client, mock_group_service):
        mock_group_service.get_group_members.return_value = [
            {"user_id": 1, "username": "test_user", "role": "owner", "joined_at": _NOW}
        ]

        resp = client.get("/groups/1/members")

        assert resp.status_code == status.HTTP_200_OK
        members = resp.json()
        assert len(members) == 1
        assert members[0]["username"] == "test_user"
        mock_group_service.require_membership.assert_called_once()

    def test_list_members_forbidden(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.require_membership.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You must be a member"
        )
        resp = client.get("/groups/1/members")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_get_member(self, client, mock_group_service):
        mock_group_service.get_group_members.return_value = [
            {"user_id": 1, "username": "test_user", "role": "owner", "joined_at": _NOW}
        ]
        resp = client.get("/groups/1/members/1")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["user_id"] == 1

    def test_get_member_not_found(self, client, mock_group_service):
        mock_group_service.get_group_members.return_value = []
        resp = client.get("/groups/1/members/99999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_add_member_success(self, client, mock_group_service):
        mock_group_service.get_group_settings.return_value = make_mock_settings()
        resp = client.post("/groups/1/members", json={"user_id": 2})
        assert resp.status_code == status.HTTP_201_CREATED
        mock_group_service.add_user.assert_called_once()

    def test_add_member_forbidden(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.get_group_settings.return_value = make_mock_settings()
        mock_group_service.require_permission.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires at least admin role"
        )
        resp = client.post("/groups/1/members", json={"user_id": 2})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_remove_member_success(self, client, mock_group_service):
        resp = client.delete("/groups/1/members/2")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_group_service.remove_user.assert_called_once()

    def test_remove_member_forbidden(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.remove_user.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires at least admin role"
        )
        resp = client.delete("/groups/1/members/2")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestGroupSearch:
    def test_search_by_name(self, client, mock_group_service):
        mock_group_service.search_groups.return_value = [make_mock_group(name="Bumblebees")]
        mock_group_service.get_user_role.return_value = None

        resp = client.get("/groups/search?query=Bumble")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()[0]["name"] == "Bumblebees"
        mock_group_service.search_groups.assert_called_once_with(
            query="Bumble", username=None, limit=10
        )

    def test_search_by_username(self, client, mock_group_service):
        mock_group_service.search_groups.return_value = [make_mock_group()]
        mock_group_service.get_user_role.return_value = None

        resp = client.get("/groups/search?username=test_user")

        assert resp.status_code == status.HTTP_200_OK
        mock_group_service.search_groups.assert_called_once_with(
            query=None, username="test_user", limit=10
        )

    def test_search_no_results(self, client, mock_group_service):
        mock_group_service.search_groups.return_value = []
        resp = client.get("/groups/search?query=zzznomatch")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

    def test_search_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/search?query=Bumble")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGroupStats:
    def test_get_stats_success(self, client, mock_group_service):
        mock_group_service.get_group_stats.return_value = {
            "member_count": 3,
            "albums_added": 10,
            "albums_reviewed": 5,
            "formed_at": _NOW,
        }

        resp = client.get("/groups/1/stats")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["member_count"] == 3
        assert data["albums_added"] == 10
        assert data["albums_reviewed"] == 5
        mock_group_service.require_membership.assert_called_once()

    def test_get_stats_non_member_forbidden(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.require_membership.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You must be a member"
        )
        resp = client.get("/groups/1/stats")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestGroupRoles:
    def test_update_role_success(self, client, mock_group_service):
        mock_group_service.get_group_members.return_value = [
            {"user_id": 2, "username": "other_user", "role": "admin", "joined_at": _NOW}
        ]
        resp = client.put("/groups/1/members/2/role", json={"role": "admin"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["role"] == "admin"
        mock_group_service.set_user_role.assert_called_once()

    def test_update_role_invalid_value(self, client):
        resp = client.put("/groups/1/members/2/role", json={"role": "superuser"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_role_forbidden(self, client, mock_group_service):
        from fastapi import HTTPException
        mock_group_service.set_user_role.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires at least admin role"
        )
        resp = client.put("/groups/1/members/2/role", json={"role": "admin"})
        assert resp.status_code == status.HTTP_403_FORBIDDEN
