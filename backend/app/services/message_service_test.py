"""Tests for MessageService."""

import pytest
from app.models import Message, Notification
from app.models.group import GroupRole
from app.schemas.message import MessageCreate
from app.schemas.notification import NotificationType
from fastapi import HTTPException, status


def _post(service, group, user, body: str) -> Message:
    return service.create_message(group.id, user, MessageCreate(body=body))


class TestCreateMessage:
    def test_create_message_success(self, message_service, sample_group, sample_user):
        message = _post(message_service, sample_group, sample_user, "great record")

        assert message.id is not None
        assert message.group_id == sample_group.id
        assert message.user_id == sample_user.id
        assert message.body == "great record"
        assert message.deleted_at is None

    def test_body_is_stripped(self, message_service, sample_group, sample_user):
        message = _post(message_service, sample_group, sample_user, "   spaced   ")
        assert message.body == "spaced"

    def test_whitespace_only_body_rejected(self):
        with pytest.raises(ValueError):
            MessageCreate(body="   ")

    def test_non_member_cannot_post(
        self, message_service, sample_group, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")

        with pytest.raises(HTTPException) as exc:
            _post(message_service, sample_group, outsider, "let me in")

        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    def test_unknown_group_404s(self, message_service, sample_user):
        with pytest.raises(HTTPException) as exc:
            message_service.create_message(
                99999, sample_user, MessageCreate(body="hello")
            )

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND


class TestMentions:
    def test_mention_of_group_member_is_recorded(
        self, message_service, sample_group, sample_user, group_member
    ):
        message = _post(
            message_service, sample_group, sample_user, f"@{group_member.username} thoughts?"
        )

        assert [m.user_id for m in message.mentions] == [group_member.id]
        assert message.mentions[0].username == group_member.username

    def test_mention_notifies_the_mentioned_user(
        self, message_service, db_session, sample_group, sample_user, group_member
    ):
        _post(message_service, sample_group, sample_user, f"hey @{group_member.username}")

        note = (
            db_session.query(Notification)
            .filter(Notification.user_id == group_member.id)
            .one()
        )
        assert note.type == NotificationType.mentioned_in_chat
        assert note.group_id == sample_group.id
        assert sample_user.username in note.message

    def test_mention_of_non_member_is_inert(
        self, message_service, db_session, sample_group, sample_user, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")

        message = _post(message_service, sample_group, sample_user, f"@{outsider.username} hi")

        # The text survives verbatim, but nobody outside the group gets pinged.
        assert message.mentions == []
        assert message.body == f"@{outsider.username} hi"
        assert db_session.query(Notification).count() == 0

    def test_unknown_handle_is_inert(
        self, message_service, db_session, sample_group, sample_user
    ):
        message = _post(message_service, sample_group, sample_user, "@nobody_at_all hello")

        assert message.mentions == []
        assert db_session.query(Notification).count() == 0

    def test_self_mention_does_not_notify(
        self, message_service, db_session, sample_group, sample_user
    ):
        message = _post(
            message_service, sample_group, sample_user, f"@{sample_user.username} note to self"
        )

        assert message.mentions == []
        assert db_session.query(Notification).count() == 0

    def test_mention_is_case_insensitive(
        self, message_service, sample_group, sample_user, group_member
    ):
        message = _post(
            message_service, sample_group, sample_user, f"@{group_member.username.upper()} hi"
        )

        assert [m.user_id for m in message.mentions] == [group_member.id]

    def test_repeated_mention_notifies_once(
        self, message_service, db_session, sample_group, sample_user, group_member
    ):
        handle = group_member.username
        _post(message_service, sample_group, sample_user, f"@{handle} @{handle} @{handle}")

        assert db_session.query(Notification).count() == 1


class TestGetHistory:
    def test_returns_oldest_first(
        self, message_service, sample_group, sample_user
    ):
        for body in ("one", "two", "three"):
            _post(message_service, sample_group, sample_user, body)

        history = message_service.get_history(sample_group.id, sample_user)

        assert [m.body for m in history] == ["one", "two", "three"]

    def test_before_pages_backwards(self, message_service, sample_group, sample_user):
        posted = [_post(message_service, sample_group, sample_user, str(i)) for i in range(5)]

        history = message_service.get_history(
            sample_group.id, sample_user, before=posted[2].id
        )

        assert [m.body for m in history] == ["0", "1"]

    def test_after_returns_only_the_delta(
        self, message_service, sample_group, sample_user
    ):
        posted = [_post(message_service, sample_group, sample_user, str(i)) for i in range(5)]

        history = message_service.get_history(
            sample_group.id, sample_user, after=posted[2].id
        )

        assert [m.body for m in history] == ["3", "4"]

    def test_limit_returns_newest_slice_in_order(
        self, message_service, sample_group, sample_user
    ):
        for i in range(10):
            _post(message_service, sample_group, sample_user, str(i))

        history = message_service.get_history(sample_group.id, sample_user, limit=3)

        # Newest three, but still chronological so the client can append.
        assert [m.body for m in history] == ["7", "8", "9"]

    def test_limit_is_clamped_to_maximum(
        self, message_service, sample_group, sample_user
    ):
        history = message_service.get_history(sample_group.id, sample_user, limit=10_000)
        assert history == []

    def test_non_member_cannot_read(
        self, message_service, sample_group, sample_user, user_factory
    ):
        _post(message_service, sample_group, sample_user, "members only")
        outsider = user_factory(email="out@test.com", username="outsider")

        with pytest.raises(HTTPException) as exc:
            message_service.get_history(sample_group.id, outsider)

        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    def test_history_is_scoped_to_one_group(
        self, message_service, sample_group, sample_user, group_factory
    ):
        other = group_factory(name="Other", user=sample_user)
        _post(message_service, sample_group, sample_user, "in first")
        _post(message_service, other, sample_user, "in second")

        history = message_service.get_history(sample_group.id, sample_user)

        assert [m.body for m in history] == ["in first"]


class TestDeleteMessage:
    def test_author_can_delete(self, message_service, sample_group, sample_user):
        message = _post(message_service, sample_group, sample_user, "oops")

        deleted = message_service.delete_message(message.id, sample_user)

        assert deleted.deleted_at is not None

    def test_delete_is_soft(
        self, message_service, db_session, sample_group, sample_user
    ):
        message = _post(message_service, sample_group, sample_user, "oops")
        message_service.delete_message(message.id, sample_user)

        # The row survives so the conversation keeps its shape.
        assert db_session.query(Message).filter(Message.id == message.id).count() == 1

    def test_group_owner_can_delete_another_users_message(
        self, message_service, sample_group, sample_user, group_member
    ):
        message = _post(message_service, sample_group, group_member, "spam")

        deleted = message_service.delete_message(message.id, sample_user)

        assert deleted.deleted_at is not None

    def test_plain_member_cannot_delete_another_users_message(
        self, message_service, sample_group, sample_user, group_member
    ):
        message = _post(message_service, sample_group, sample_user, "mine")

        with pytest.raises(HTTPException) as exc:
            message_service.delete_message(message.id, group_member)

        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    def test_group_admin_can_delete(
        self, message_service, sample_group, sample_user, group_member, set_user_role
    ):
        message = _post(message_service, sample_group, sample_user, "moderate me")
        set_user_role(
            user_id=group_member.id, group_id=sample_group.id, role=GroupRole.Admin
        )

        deleted = message_service.delete_message(message.id, group_member)

        assert deleted.deleted_at is not None

    def test_deleting_twice_is_idempotent(
        self, message_service, sample_group, sample_user
    ):
        message = _post(message_service, sample_group, sample_user, "oops")

        first = message_service.delete_message(message.id, sample_user)
        first_stamp = first.deleted_at
        second = message_service.delete_message(message.id, sample_user)

        assert second.deleted_at == first_stamp

    def test_unknown_message_404s(self, message_service, sample_user):
        with pytest.raises(HTTPException) as exc:
            message_service.delete_message(99999, sample_user)

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND


class TestSerializeMessage:
    def test_serializes_author_and_mentions(
        self, message_service, sample_group, sample_user, group_member
    ):
        from app.services.message_service import serialize_message

        message = _post(
            message_service, sample_group, sample_user, f"@{group_member.username} hi"
        )
        payload = serialize_message(message)

        assert payload.username == sample_user.username
        assert payload.is_deleted is False
        assert [m.username for m in payload.mentions] == [group_member.username]

    def test_deleted_message_withholds_its_body(
        self, message_service, sample_group, sample_user, group_member
    ):
        from app.services.message_service import serialize_message

        message = _post(
            message_service, sample_group, sample_user, f"@{group_member.username} secret"
        )
        message_service.delete_message(message.id, sample_user)

        payload = serialize_message(message_service.get_message(message.id))

        assert payload.is_deleted is True
        assert payload.body == ""
        assert payload.mentions == []
