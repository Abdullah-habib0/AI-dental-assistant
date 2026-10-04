"""Passwords and login tickets.

Two different kinds of token live here, and they work in completely different ways:

  access token   A signed ticket (a JWT). The server can check it is genuine just by
                 looking at the signature, without touching the database. Fast, but it
                 cannot be cancelled - it stays valid until it expires.

  refresh token  Just a long random string. It means nothing on its own; it only works
                 if a matching row exists in the database. That is what makes logout
                 real: delete the row and the token is dead immediately.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

# bcrypt ignores anything past 72 bytes. Two different long passwords could then open
# the same account, so we refuse them instead of silently cutting them short.
MAX_PASSWORD_BYTES = 72


def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if password_too_long(password):
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def read_access_token(token: str) -> int | None:
    """Give back the user id inside the ticket, or None if it is fake or expired."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None


def new_refresh_token() -> str:
    """A long random string. 48 bytes is far too much to ever be guessed."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Only the hash is stored, so a leaked database hands over no working tokens.

    Plain SHA-256 is right here, unlike for passwords. Passwords need a deliberately
    slow hash because people choose guessable ones. This token is 48 random bytes -
    there is nothing to guess, so slowing it down would buy nothing.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    """Stored without a timezone label, like every other time in the database."""
    return (datetime.now(UTC) + timedelta(days=settings.refresh_token_days)).replace(
        tzinfo=None
    )
