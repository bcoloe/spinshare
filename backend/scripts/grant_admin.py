"""Bootstrap script to grant admin status to an initial user.

Run from the backend/ directory:
    python scripts/grant_admin.py --username alice
    python scripts/grant_admin.py --email alice@example.com

This is the only way to create the first admin; subsequent grants should go
through the PUT /users/{user_id}/admin API endpoint.
"""

import argparse
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant admin status to a user")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--username", help="Username of the target user")
    group.add_argument("--email", help="Email of the target user")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.username:
            user = db.query(User).filter(User.username == args.username.lower()).first()
            identifier = f"username '{args.username}'"
        else:
            user = db.query(User).filter(User.email == args.email.lower()).first()
            identifier = f"email '{args.email}'"

        if not user:
            print(f"Error: No user found with {identifier}", file=sys.stderr)
            sys.exit(1)

        if user.is_admin:
            print(f"User '{user.username}' is already an admin — nothing to do.")
            return

        user.is_admin = True
        db.commit()
        print(f"Granted admin to '{user.username}' (id={user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
