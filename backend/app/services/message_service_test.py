"""Tests for MessageService."""

import pytest
from app.models import Message, Notification
from app.models.group import GroupRole, group_members
from app.schemas.message import MessageCreate
from app.schemas.notification import NotificationType
from fastapi import HTTPException, status
from sqlalchemy import select


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


class TestUnreadCounts:
    def test_counts_messages_from_others(
        self, message_service, sample_group, sample_user, group_member
    ):
        for body in ("one", "two", "three"):
            _post(message_service, sample_group, sample_user, body)

        assert message_service.unread_counts(group_member) == {sample_group.id: 3}

    def test_ignores_your_own_messages(
        self, message_service, sample_group, sample_user, group_member
    ):
        _post(message_service, sample_group, sample_user, "mine")
        _post(message_service, sample_group, group_member, "also mine")

        # sample_user sees only group_member's message, and vice versa.
        assert message_service.unread_counts(sample_user) == {sample_group.id: 1}
        assert message_service.unread_counts(group_member) == {sample_group.id: 1}

    def test_groups_with_nothing_unread_are_omitted(
        self, message_service, sample_group, group_member
    ):
        assert message_service.unread_counts(group_member) == {}

    def test_marking_seen_clears_the_count(
        self, message_service, sample_group, sample_user, group_member
    ):
        posted = [_post(message_service, sample_group, sample_user, str(i)) for i in range(3)]

        message_service.mark_chat_seen(sample_group.id, group_member, posted[-1].id)

        assert message_service.unread_counts(group_member) == {}

    def test_counts_only_what_arrived_after_the_marker(
        self, message_service, sample_group, sample_user, group_member
    ):
        posted = [_post(message_service, sample_group, sample_user, str(i)) for i in range(5)]

        message_service.mark_chat_seen(sample_group.id, group_member, posted[1].id)

        assert message_service.unread_counts(group_member) == {sample_group.id: 3}

    def test_deleted_messages_do_not_count(
        self, message_service, sample_group, sample_user, group_member
    ):
        first = _post(message_service, sample_group, sample_user, "oops")
        _post(message_service, sample_group, sample_user, "kept")

        message_service.delete_message(first.id, sample_user)

        assert message_service.unread_counts(group_member) == {sample_group.id: 1}

    def test_a_deleted_authors_message_still_counts(
        self, message_service, db_session, sample_group, sample_user, group_member
    ):
        # user_id goes null when the author deletes their account. A naive
        # `user_id != me` would evaluate to null and silently drop the row.
        message = _post(message_service, sample_group, sample_user, "orphaned")
        message.user_id = None
        db_session.commit()

        assert message_service.unread_counts(group_member) == {sample_group.id: 1}

    def test_counts_are_reported_per_group(
        self, message_service, db_session, sample_group, sample_user, group_member, group_factory
    ):
        other = group_factory(name="Other", user=sample_user)
        db_session.execute(
            group_members.insert().values(
                group_id=other.id, user_id=group_member.id, role=GroupRole.Member.value
            )
        )
        db_session.commit()
        _post(message_service, sample_group, sample_user, "here")
        for body in ("a", "b"):
            _post(message_service, other, sample_user, body)

        assert message_service.unread_counts(group_member) == {
            sample_group.id: 1,
            other.id: 2,
        }

    def test_groups_you_are_not_in_are_invisible(
        self, message_service, sample_group, sample_user, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")
        _post(message_service, sample_group, sample_user, "members only")

        assert message_service.unread_counts(outsider) == {}

    def test_a_new_member_does_not_inherit_the_backlog(
        self, message_service, sample_group, sample_user, user_factory
    ):
        for body in ("old one", "old two"):
            _post(message_service, sample_group, sample_user, body)

        # Joining through the real path, after those messages were posted.
        latecomer = user_factory(email="late@test.com", username="latecomer")
        message_service.group_service.add_user(sample_group.id, latecomer.id)

        assert message_service.unread_counts(latecomer) == {}

        _post(message_service, sample_group, sample_user, "after you joined")
        assert message_service.unread_counts(latecomer) == {sample_group.id: 1}

    def test_joining_an_empty_room_counts_everything_after(
        self, message_service, sample_group, sample_user, user_factory
    ):
        early = user_factory(email="early@test.com", username="earlybird")
        message_service.group_service.add_user(sample_group.id, early.id)

        _post(message_service, sample_group, sample_user, "first ever")

        assert message_service.unread_counts(early) == {sample_group.id: 1}


class TestReadMarker:
    def _marker(self, db_session, group_id, user_id):
        return db_session.execute(
            select(group_members.c.last_read_message_id).where(
                group_members.c.group_id == group_id,
                group_members.c.user_id == user_id,
            )
        ).scalar()

    def test_advances_to_the_given_message(
        self, message_service, db_session, sample_group, sample_user, group_member
    ):
        message = _post(message_service, sample_group, sample_user, "hello")

        message_service.mark_chat_seen(sample_group.id, group_member, message.id)

        assert self._marker(db_session, sample_group.id, group_member.id) == message.id

    def test_never_moves_backwards(
        self, message_service, db_session, sample_group, sample_user, group_member
    ):
        posted = [_post(message_service, sample_group, sample_user, str(i)) for i in range(3)]

        message_service.mark_chat_seen(sample_group.id, group_member, posted[2].id)
        # A stale second tab reports an older position — it must not rewind.
        message_service.mark_chat_seen(sample_group.id, group_member, posted[0].id)

        assert self._marker(db_session, sample_group.id, group_member.id) == posted[2].id

    def test_omitting_the_id_leaves_the_marker_alone(
        self, message_service, db_session, sample_group, sample_user, group_member
    ):
        message = _post(message_service, sample_group, sample_user, "hello")
        message_service.mark_chat_seen(sample_group.id, group_member, message.id)

        message_service.mark_chat_seen(sample_group.id, group_member)

        assert self._marker(db_session, sample_group.id, group_member.id) == message.id

    def test_is_per_member(
        self, message_service, db_session, sample_group, sample_user, group_member
    ):
        message = _post(message_service, sample_group, sample_user, "hello")

        message_service.mark_chat_seen(sample_group.id, group_member, message.id)

        assert self._marker(db_session, sample_group.id, sample_user.id) is None

    def test_non_member_cannot_advance_a_marker(
        self, message_service, sample_group, user_factory
    ):
        outsider = user_factory(email="out@test.com", username="outsider")

        with pytest.raises(HTTPException) as exc:
            message_service.mark_chat_seen(sample_group.id, outsider, 1)

        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


class TestMarkChatSeen:
    def test_clears_unread_mentions_for_the_group(
        self, message_service, sample_group, sample_user, group_member
    ):
        _post(message_service, sample_group, sample_user, f"@{group_member.username} listen")
        assert len(message_service.notification_service.get_unread(group_member)) == 1

        cleared = message_service.mark_chat_seen(sample_group.id, group_member)

        assert cleared == 1
        assert message_service.notification_service.get_unread(group_member) == []

    def test_leaves_other_groups_alone(
        self, message_service, sample_group, sample_user, group_member, db_session, group_factory
    ):
        other = group_factory(name="Other", user=sample_user)
        db_session.execute(
            group_members.insert().values(
                group_id=other.id, user_id=group_member.id, role=GroupRole.Member.value
            )
        )
        db_session.commit()
        _post(message_service, sample_group, sample_user, f"@{group_member.username} here")
        _post(message_service, other, sample_user, f"@{group_member.username} and here")

        message_service.mark_chat_seen(sample_group.id, group_member)

        remaining = message_service.notification_service.get_unread(group_member)
        assert [n.group_id for n in remaining] == [other.id]

    def test_leaves_other_notification_types_alone(
        self, message_service, sample_group, group_member, db_session
    ):
        # Watching chat should not silently dismiss an unrelated notification
        # that happens to point at the same group.
        review = Notification(
            user_id=group_member.id,
            type=NotificationType.member_reviewed_album,
            message="someone reviewed an album",
            group_id=sample_group.id,
        )
        db_session.add(review)
        db_session.commit()

        cleared = message_service.mark_chat_seen(sample_group.id, group_member)

        assert cleared == 0
        unread = message_service.notification_service.get_unread(group_member)
        assert [n.type for n in unread] == [NotificationType.member_reviewed_album]

    def test_leaves_other_users_alone(
        self, message_service, sample_group, sample_user, group_member
    ):
        _post(message_service, sample_group, sample_user, f"@{group_member.username} hi")

        message_service.mark_chat_seen(sample_group.id, sample_user)

        assert len(message_service.notification_service.get_unread(group_member)) == 1

    def test_is_idempotent(self, message_service, sample_group, sample_user, group_member):
        _post(message_service, sample_group, sample_user, f"@{group_member.username} hi")

        assert message_service.mark_chat_seen(sample_group.id, group_member) == 1
        assert message_service.mark_chat_seen(sample_group.id, group_member) == 0

    def test_non_member_cannot_clear(self, message_service, sample_group, user_factory):
        outsider = user_factory(email="out@test.com", username="outsider")

        with pytest.raises(HTTPException) as exc:
            message_service.mark_chat_seen(sample_group.id, outsider)

        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


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
