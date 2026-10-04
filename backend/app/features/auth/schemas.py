from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES, password_too_long


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def password_must_fit(cls, value: str) -> str:
        # Checked in bytes, not characters. Accented letters and emoji take up more than
        # one byte each, so a 40-character password can still be over the limit.
        if password_too_long(value):
            raise ValueError(
                f"Password is too long (limit is {MAX_PASSWORD_BYTES} bytes)."
            )
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    """What you get back from register and login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenOnly(BaseModel):
    """What you get back from refresh. The refresh token you sent stays valid."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
