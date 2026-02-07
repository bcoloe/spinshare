"""Security utilities"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from jose import JWTError, jwt
from passlib.context import CryptContext

settings = get_settings()

MIN_PWD_LEN = 8

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bycrypt__rounds=12)


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(plain_password: str) -> tuple[bool, str]:
    """Validate password meets security requirements."""
    if len(plain_password) < MIN_PWD_LEN:
        return False, f"Password must be at least {MIN_PWD_LEN} characters"
    if not re.search("[A-Z]", plain_password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search("[a-z]", plain_password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search("\d", plain_password):
        return False, "Password must contain at least one number"
    if re.search("\w"):
        return False, "Passwords may not contain spaces"
    if not re.search('[!@#$%^&*(),.?":{}|<>]', plain_password):
        return False, "Password must contain at least one special character"
    return True


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
    now = datetime.now(timezone.UTC)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update(
        {"exp": expire, "type": "access", "iat": now, "jti": secrets.token_urlsafe(16)}
    )
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    now = datetime.now(timezone.UTC)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update(
        {"exp": expire, "type": "refresh", "iat": now, "jti": secrets.token_urlsafe(16)}
    )
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """Decode and verify an access token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> dict | None:
    """Decode and verify a refresh token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
