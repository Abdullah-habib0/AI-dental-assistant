"""The rules for register, login, refresh and logout.

Every function here owns its transaction, so an operation either finishes completely or
leaves nothing behind.
"""

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.time import utcnow
from app.features.auth import repository
from app.features.auth.models import RefreshToken, User
from app.features.auth.schemas import LoginRequest, RegisterRequest

# Used to keep the login check slow even when the email does not exist. Without it, a
# wrong email answers instantly while a wrong password takes a moment, and that small
# difference tells an attacker which email addresses have accounts here.
_DUMMY_HASH = security.hash_password(secrets.token_urlsafe(16))


class EmailAlreadyUsed(Exception):
    pass


class BadCredentials(Exception):
    pass


class BadRefreshToken(Exception):
    pass


def _tidy_email(email: str) -> str:
    """Store one form only, so Ali@x.com and ali@x.com cannot become two accounts."""
    return email.strip().lower()


async def _issue_refresh_token(session: AsyncSession, user_id: int) -> str:
    raw = security.new_refresh_token()
    repository.add_refresh_token(
        session,
        RefreshToken(
            user_id=user_id,
            token_hash=security.hash_refresh_token(raw),
            expires_at=security.refresh_token_expiry(),
        ),
    )
    # The caller gets the real token. Only its hash is ever written down.
    return raw


async def register(
    session: AsyncSession, data: RegisterRequest
) -> tuple[User, str, str]:
    email = _tidy_email(data.email)

    async with session.begin():
        if await repository.get_user_by_email(session, email) is not None:
            raise EmailAlreadyUsed("That email address is already registered.")

        user = User(
            email=email,
            password_hash=security.hash_password(data.password),
            full_name=data.full_name.strip(),
        )
        repository.add_user(session, user)

        # Writes the user so the database hands back its id, which the refresh token
        # needs. Still inside the transaction - nothing is final until it closes.
        await session.flush()

        refresh_token = await _issue_refresh_token(session, user.id)
        access_token = security.create_access_token(user.id)

    return user, access_token, refresh_token


async def login(session: AsyncSession, data: LoginRequest) -> tuple[User, str, str]:
    email = _tidy_email(data.email)

    async with session.begin():
        user = await repository.get_user_by_email(session, email)

        # Always check a password, even when there is no such user, so both answers
        # take the same amount of time.
        password_hash = user.password_hash if user else _DUMMY_HASH
        password_ok = security.verify_password(data.password, password_hash)

        if user is None or not password_ok:
            raise BadCredentials("Email or password is wrong.")

        refresh_token = await _issue_refresh_token(session, user.id)
        access_token = security.create_access_token(user.id)

    return user, access_token, refresh_token


async def refresh(session: AsyncSession, raw_token: str) -> str:
    """Swap a refresh token for a new access token. The refresh token stays valid."""
    token_hash = security.hash_refresh_token(raw_token)

    async with session.begin():
        stored = await repository.get_refresh_token(session, token_hash)
        if stored is None:
            raise BadRefreshToken("That refresh token is not valid.")

        if stored.expires_at <= utcnow():
            # Expired, so clear it out rather than leaving dead rows behind.
            await repository.delete_refresh_token(session, token_hash)
            raise BadRefreshToken("That refresh token has expired. Please log in again.")

        return security.create_access_token(stored.user_id)


async def logout(session: AsyncSession, raw_token: str) -> None:
    """Deleting the row is what actually ends the session.

    No error if the token was already gone. Logging out twice is not a problem, and
    saying "that token did not exist" would only tell a stranger which tokens are real.
    """
    async with session.begin():
        await repository.delete_refresh_token(
            session, security.hash_refresh_token(raw_token)
        )
