"""Security utilities"""

import dataclasses
import enum
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import get_settings
from jose import JWTError, jwt
from passlib.context import CryptContext

settings = get_settings()

MIN_PWD_LEN = 8
MAX_PWD_LEN = 50

# Password hashing with bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12  # Explicit cost factor
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Bcrypt handles everything - no need for pre-hashing
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash"""
    return pwd_context.verify(plain_password, hashed_password)


@dataclasses.dataclass
class TestCondition:
    """Test conditions that takes a single argument and evaluates validity

    Args:
        reason (str): Explanation of failure.
        check (callable): Predicate check that returns pass/fail provided a single argument.
    """

    reason: str
    check: Callable[[Any], bool]


class PasswordStrengthConditions(enum.Enum):
    """Password strength evaluation conditions."""

    Length = TestCondition(
        f"Password size much be [{MIN_PWD_LEN}, {MAX_PWD_LEN}] characters",
        lambda x: len(x) >= MIN_PWD_LEN and len(x) <= MAX_PWD_LEN,
    )
    UppercaseLetter = TestCondition(
        "Password must contain at least one uppercase letter",
        lambda x: bool(re.search(r"[A-Z]", x)),
    )
    LowercaseLetter = TestCondition(
        "Password must contain at least one lowercase letter",
        lambda x: bool(re.search(r"[a-z]", x)),
    )
    Number = TestCondition(
        "Password must contain at least one number", lambda x: bool(re.search(r"\d", x))
    )
    NoSpaces = TestCondition(
        "Passwords may not contain spaces", lambda x: not bool(re.search(r"\s", x))
    )
    SpecialCharacters = TestCondition(
        "Password must contain at least one special character",
        lambda x: bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', x)),
    )


def validate_password_strength(plain_password: str) -> tuple[bool, list[str]]:
    """Validate password meets security requirements."""
    reasons: list[str] = []
    for condition in PasswordStrengthConditions:
        if not condition.value.check(plain_password):
            reasons.append(condition.value.reason)
    return len(reasons) == 0, reasons


# JWT tokens
SECRET_KEY = settings.SECRET_KEY
if len(SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY must be at least 32 characters long")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update(
        {"exp": expire, "type": "access", "iat": now, "jti": secrets.token_urlsafe(16)}
    )
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    to_encode.update(
        {"exp": expire, "type": "refresh", "iat": now, "jti": secrets.token_urlsafe(16)}
    )
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str, *, verify_exp: bool = True) -> dict | None:
    """Decode and verify an access token

    Args:
        token (str): Token to decode.
        verify_exp (optional, bool): TEST ONLY, used to disable verification of expiration for
            testing purposes.
    """
    try:
        options = {"verify_exp": verify_exp}
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options=options)
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str, *, verify_exp: bool = True) -> dict | None:
    """Decode and verify a refresh token"""
    try:
        options = {"verify_exp": verify_exp}
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options=options)

        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
