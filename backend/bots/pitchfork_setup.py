"""One-time setup for the Pitchfork Best New Albums bot.

Run once per environment before the first cron execution:
    python bots/pitchfork_setup.py

Safe to re-run — checks for existing records before creating anything.
"""

import logging
import sys

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import BotSource, Group, GroupSettings, User  # noqa: F401 — register all models
from bots.shared import setup_bot_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BOT_USERNAME = "pitchfork-bot"
BOT_EMAIL = "pitchfork-bot@spinshare.internal"
GROUP_NAME = "Pitchfork Best New Albums"
BOT_SOURCE_NAME = "pitchfork_best_new"


def main():
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        bot_user, group, bot_source = setup_bot_source(
            db,
            username=BOT_USERNAME,
            email=BOT_EMAIL,
            group_name=GROUP_NAME,
            source_name=BOT_SOURCE_NAME,
        )
        print(f"\nSetup complete:")
        print(f"  Bot user id : {bot_user.id}  ({bot_user.username})")
        print(f"  Bot group id: {group.id}  ({group.name})")
        print(f"  BotSource id: {bot_source.id}  ({bot_source.name})")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
