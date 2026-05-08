"""One-time setup: creates the Pitchfork bot user, group, and BotSource record.

Run once per environment (dev, staging, prod) before the first cron execution:
    python scripts/setup_bot.py

Safe to re-run — checks for existing records before creating anything.
"""

import secrets
import sys

# Ensure the app package is importable when run from the backend/ directory.
sys.path.insert(0, ".")

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import BotSource, Group, GroupSettings, User  # noqa: F401 — register all models
from app.models.group import GroupRole, group_members
from app.models.group_settings import GroupSettings
from app.utils.security import hash_password
from sqlalchemy import insert, select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_USERNAME = "pitchfork-bot"
BOT_EMAIL = "pitchfork-bot@spinshare.internal"
GROUP_NAME = "Pitchfork Best New Albums"
BOT_SOURCE_NAME = "pitchfork_best_new"


def run(db):
    # 1. Bot user
    bot_user = db.query(User).filter(User.username == BOT_USERNAME).first()
    if bot_user:
        log.info("Bot user already exists: id=%d", bot_user.id)
    else:
        bot_user = User(
            email=BOT_EMAIL,
            username=BOT_USERNAME,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            is_bot=True,
        )
        db.add(bot_user)
        db.commit()
        db.refresh(bot_user)
        log.info("Created bot user: id=%d username=%s", bot_user.id, bot_user.username)

    # 2. Bot group
    group = db.query(Group).filter(Group.name == GROUP_NAME).first()
    if group:
        log.info("Bot group already exists: id=%d", group.id)
    else:
        group = Group(name=GROUP_NAME, is_public=True, created_by=bot_user.id)
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

    # 4. Group settings — allow_guessing=False so bot nominations skip the guessing game
    settings = db.query(GroupSettings).filter(GroupSettings.group_id == group.id).first()
    if settings:
        if settings.allow_guessing:
            settings.allow_guessing = False
            db.commit()
            log.info("Updated group settings: allow_guessing=False")
        else:
            log.info("Group settings already correct")
    else:
        settings = GroupSettings(group_id=group.id, allow_guessing=False)
        db.add(settings)
        db.commit()
        log.info("Created group settings with allow_guessing=False")

    # 5. BotSource record
    bot_source = db.query(BotSource).filter(BotSource.name == BOT_SOURCE_NAME).first()
    if bot_source:
        log.info("BotSource already exists: id=%d", bot_source.id)
    else:
        bot_source = BotSource(
            name=BOT_SOURCE_NAME,
            bot_user_id=bot_user.id,
            bot_group_id=group.id,
            processing_state={"last_processed_page": 0},
        )
        db.add(bot_source)
        db.commit()
        db.refresh(bot_source)
        log.info("Created BotSource: id=%d name=%s", bot_source.id, bot_source.name)

    print(f"\nSetup complete:")
    print(f"  Bot user id : {bot_user.id}  ({bot_user.username})")
    print(f"  Bot group id: {group.id}  ({group.name})")
    print(f"  BotSource id: {bot_source.id}  ({bot_source.name})")


def main():
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
