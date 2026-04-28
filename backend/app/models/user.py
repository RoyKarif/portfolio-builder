"""User ORM model — represents a row in the `users` table.

A User is anyone who registered. We store only what's strictly needed
for auth: email and a bcrypt hash. No first-name, last-name, role, etc.
— YAGNI.
"""

from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    """A registered user."""

    __tablename__ = "users"

    # Auto-incrementing primary key. SERIAL in Postgres, BIGSERIAL would
    # be overkill for a tutorial-grade app — INTEGER caps at 2.1B users
    # which is plenty.
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Email is the login identifier. unique=True creates a UNIQUE
    # constraint at the DB level, so concurrent registrations cannot
    # produce duplicates even if the application code has a race.
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    # bcrypt hash. NEVER store the plaintext password.
    # bcrypt hashes are always 60 chars, but we allow more to be future-proof
    # (e.g. if we migrate to argon2).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Account creation time. Used for analytics, "delete inactive accounts"
    # policies, and forensics. default=datetime.utcnow runs in Python at
    # INSERT time — predictable and DB-agnostic.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        # Useful for debugging in pytest/REPL. NEVER include password_hash.
        return f"<User id={self.id} email={self.email!r}>"
