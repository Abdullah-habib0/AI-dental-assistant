"""Database queries for auth.

Nothing here commits. Adding and deleting is fine - it is saving that belongs to
service.py, so that a whole operation succeeds or fails as one piece.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import RefreshToken, User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


def add_user(session: AsyncSession, user: User) -> None:
    session.add(user)


async def get_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    return await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )


def add_refresh_token(session: AsyncSession, token: RefreshToken) -> None:
    session.add(token)


async def delete_refresh_token(session: AsyncSession, token_hash: str) -> int:
    """Returns how many rows were removed, so logout can tell if the token was real."""
    result = await session.execute(
        delete(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    return result.rowcount or 0
