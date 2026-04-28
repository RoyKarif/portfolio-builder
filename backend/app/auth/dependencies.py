"""FastAPI dependencies that wire up authentication.

`get_current_user` is the dependency used by any protected endpoint:

    @router.get("/me")
    def me(user: User = Depends(get_current_user)):
        return user

FastAPI will run get_current_user before me() — extracting the JWT from
the Authorization header, verifying it, and loading the User from the DB.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token, TokenInvalid
from app.data.user_repo import get_user_by_id
from app.db import get_db
from app.models.user import User


# OAuth2PasswordBearer extracts the token from `Authorization: Bearer <token>`.
# tokenUrl points to where the token is issued — used by FastAPI's interactive
# /docs UI to show a "Login" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the JWT to a User, or raise 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_token(token)
    except TokenInvalid:
        raise credentials_exception

    user = get_user_by_id(db, user_id)
    if user is None:
        # Token is valid but the user no longer exists (deleted account).
        raise credentials_exception

    return user
