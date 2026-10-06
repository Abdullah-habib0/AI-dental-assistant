from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiting import auth_per_minute
from app.db.session import get_session
from app.features.auth import service
from app.features.auth.dependencies import CurrentUser
from app.features.auth.schemas import (
    AccessTokenOnly,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_Session = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_per_minute)],
)
async def register(data: RegisterRequest, session: _Session):
    try:
        _user, access_token, refresh_token = await service.register(session, data)
    except service.EmailAlreadyUsed as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(auth_per_minute)])
async def login(data: LoginRequest, session: _Session):
    try:
        _user, access_token, refresh_token = await service.login(session, data)
    except service.BadCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenOnly)
async def refresh(data: RefreshRequest, session: _Session):
    try:
        access_token = await service.refresh(session, data.refresh_token)
    except service.BadRefreshToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    return AccessTokenOnly(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, session: _Session):
    await service.logout(session, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    """Lets the website find out whether the visitor is logged in, and who they are."""
    return user
