"""User repository — DB access for the `users` table."""

from sqlalchemy.orm import Session
from app.models.user import User


def create_user(db: Session, email: str, password_hash: str) -> User:
    """Insert a new user. Caller is responsible for hashing the password.

    Raises sqlalchemy.exc.IntegrityError if email already exists
    (the UNIQUE constraint at the DB level catches this).
    """
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)  # populate auto-generated fields (id, created_at)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Look up a user by email (used during login). Returns None if absent."""
    return db.query(User).filter(User.email == email).one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Look up a user by id (used by JWT auth dependency)."""
    return db.query(User).filter(User.id == user_id).one_or_none()
