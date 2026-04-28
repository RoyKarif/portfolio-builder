"""Auth-related request/response schemas."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Body of POST /api/auth/register."""

    # EmailStr validates RFC-5322 format. Pydantic uses email-validator
    # under the hood (transitive dep, no extra install).
    email: EmailStr

    # Min length 8 — basic safety. We don't enforce complexity here;
    # bcrypt makes weak passwords expensive enough to attack.
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    """Body of POST /api/auth/login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    """Returned by /register and /login. Standard OAuth2 shape."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user info (never includes password_hash)."""

    id: int
    email: EmailStr
    created_at: datetime

    # Allows constructing from an ORM object via `UserResponse.model_validate(user)`.
    model_config = {"from_attributes": True}
