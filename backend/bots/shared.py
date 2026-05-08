"""Shared setup utility for bot users.

Any bot's setup script calls setup_bot_source() with its specific config.
The function is idempotent — safe to re-run in any environment.

Example (future Rolling Stone bot):
    from bots.shared import setup_bot_source
    bot_user, group, bot_source = setup_bot_source(
        db,
        username="rolling-stone-bot",
        email="rolling-stone-bot@spinshare.internal",
        group_name="Rolling Stone 500 Greatest Albums",
        source_name="rolling_stone_500",
    )
"""

import logging
import secrets

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.models import BotSource, Group, GroupSettings, User
from app.models.group import GroupRole, group_members
from app.utils.security import hash_password

log = logging.getLogger(__name__)


def setup_bot_source(
    db: Session,
    *,
    username: str,
    email: str,
    group_name: str,
    source_name: str,
) -> tuple[User, Group, BotSource]:
    """Idempotent setup: creates the bot user, group, and BotSource if they don't exist.

    Returns (bot_user, group, bot_source).
    """
    # 1. Bot user
    bot_user = db.query(User).filter(User.username == username).first()
    if bot_user:
        log.info("Bot user already exists: id=%d", bot_user.id)
    else:
        bot_user = User(
            email=email,
            username=username,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            is_bot=True,
        )
        db.add(bot_user)
        db.commit()
        db.refresh(bot_user)
        log.info("Created bot user: id=%d username=%s", bot_user.id, bot_user.username)

    # 2. Bot group
    group = db.query(Group).filter(Group.name == group_name).first()
    if group:
        log.info("Bot group already exists: id=%d", group.id)
    else:
        group = Group(name=group_name, is_public=True, created_by=bot_user.id)
        db.add(group)
        db.commit()
        db.refresh(group)
        log.info("Created bot group: id=%d name=%r", group.id, group.name)

    # 3. Group membership + Owner role
    existing = db.execute(
        select(group_members).where(
            group_members.c.group_id == group.id,
            group_members.c.user_id == bot_user.id,
        )
    ).first()
    if existing:
        log.info("Bot user already a member of group %d", group.id)
    else:
        db.execute(
            insert(group_members).values(
                group_id=group.id,
                user_id=bot_user.id,
                role=GroupRole.Owner.value,
            )
        )
        db.commit()
        log.info("Added bot user to group %d with Owner role", group.id)

    # 4. Group settings — disable guessing and lock nominations to owner (bot) only
    settings = db.query(GroupSettings).filter(GroupSettings.group_id == group.id).first()
    if settings:
        changed = []
        if settings.allow_guessing:
            settings.allow_guessing = False
            changed.append("allow_guessing=False")
        if settings.min_role_to_nominate != "owner":
            settings.min_role_to_nominate = "owner"
            changed.append("min_role_to_nominate=owner")
        if changed:
            db.commit()
            log.info("Updated group settings: %s", ", ".join(changed))
        else:
            log.info("Group settings already correct")
    else:
        settings = GroupSettings(group_id=group.id, allow_guessing=False, min_role_to_nominate="owner")
        db.add(settings)
        db.commit()
        log.info("Created group settings with allow_guessing=False, min_role_to_nominate=owner")

    # 5. BotSource record
    bot_source = db.query(BotSource).filter(BotSource.name == source_name).first()
    if bot_source:
        log.info("BotSource already exists: id=%d", bot_source.id)
    else:
        bot_source = BotSource(
            name=source_name,
            bot_user_id=bot_user.id,
            bot_group_id=group.id,
            processing_state={},
        )
        db.add(bot_source)
        db.commit()
        db.refresh(bot_source)
        log.info("Created BotSource: id=%d name=%s", bot_source.id, bot_source.name)

    return bot_user, group, bot_source
