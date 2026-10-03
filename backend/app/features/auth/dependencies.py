"""Two ways to ask "who is making this request?".

    get_current_user           demands a login, refuses the request without one
    get_current_user_optional  returns the user, or None if nobody is logged in

The second one is what makes login optional for booking: the chat works for a guest,
and quietly links the appointment to an account when there is one.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import read_access_token
from app.db.session import SessionLocal
from app.features.auth import repository
from app.features.auth.models import User

# auto_error=False so a missing header returns None instead of raising. The optional
# version needs that; the strict version raises its own error below.
_bearer = HTTPBearer(auto_error=False)

_Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


async def get_current_user_optional(credentials: _Credentials) -> User | None:
    if credentials is None:
        return None

    user_id = read_access_token(credentials.credentials)
    if user_id is None:
        return None

    # Uses its own short session, NOT the request's. FastAPI would otherwise hand the
    # same session to the route, and this lookup would leave a transaction open in it.
    # The booking code then can't open its own, and every logged-in booking fails.
    async with SessionLocal() as session:
        return await repository.get_user_by_id(session, user_id)


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not logged in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
