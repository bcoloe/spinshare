#!/usr/bin/env python
"""Quick smoke-test for email sending. Run from the backend directory:

    python scripts/test_email.py recipient@example.com
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import get_settings
from app.utils.email import send_invitation_email

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))

def main():
    to_email = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    settings = get_settings(env_file=os.path.join(BACKEND_DIR, ".env"))

    print(f"SMTP_ENABLED : {settings.SMTP_ENABLED}")
    print(f"SMTP_HOST    : {settings.SMTP_HOST!r}")
    print(f"SMTP_PORT    : {settings.SMTP_PORT}")
    print(f"SMTP_FROM    : {settings.SMTP_FROM!r}")
    print(f"To           : {to_email}")
    print()

    if not settings.SMTP_ENABLED:
        print("SMTP_ENABLED is False — set it to true in .env and try again.")
        sys.exit(1)

    send_invitation_email(
        to_email=to_email,
        group_name="Test Group",
        inviter_username="testuser",
        invite_url=f"{settings.FRONTEND_URL}/invite/test-token-abc123",
    )
    print("Done — check your inbox or Mailpit at http://localhost:8025")

if __name__ == "__main__":
    main()
