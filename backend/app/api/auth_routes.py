"""Auth endpoints: register and login."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_password
from app.data.user_repo import create_user, get_user_by_email
from app.db import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Create a new account and return an access token immediately.

    Returning the token here saves the user a separate login round-trip.
    """
    try:
        user = create_user(
            db,
            email=request.email,
            password_hash=hash_password(request.password),
        )
    except IntegrityError:
        # The UNIQUE constraint on email rejected the insert.
        # Generic message — don't reveal whether email exists (privacy).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create account",
        )

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verify email+password and return an access token.

    Returns a generic 401 for both "no such email" and "wrong password" —
    don't leak whether an email is registered.
    """
    user = get_user_by_email(db, request.email)
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return TokenResponse(access_token=create_access_token(user.id))
