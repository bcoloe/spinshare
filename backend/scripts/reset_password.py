"""Admin script to reset a user's password directly in the database.

Run from the backend/ directory:
    python scripts/reset_password.py --email alice@example.com --password NewPass123
    python scripts/reset_password.py --username alice --password NewPass123

Relay the new password to the user out-of-band; they can change it via the
profile settings page once logged in.
"""

import argparse
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.security import hash_password, validate_password_strength  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a user's password")
    id_group = parser.add_mutually_exclusive_group(required=True)
    id_group.add_argument("--username", help="Username of the target user")
    id_group.add_argument("--email", help="Email of the target user")
    parser.add_argument("--password", required=True, help="New plaintext password")
    args = parser.parse_args()

    # Validate strength before touching the DB
    is_valid, reasons = validate_password_strength(args.password)
    if not is_valid:
        print("Error: password does not meet requirements:", file=sys.stderr)
        for r in reasons:
            print(f"  * {r}", file=sys.stderr)
        sys.exit(1)

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

        user.password_hash = hash_password(args.password)
        db.commit()
        print(f"Password reset for '{user.username}' (id={user.id}, email={user.email}).")
        print("Relay the new password to the user — they can change it via profile settings.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
