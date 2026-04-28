"""Database session factory and the FastAPI dependency that hands
sessions to endpoints.

Three things live here:
  1. The SQLAlchemy engine — the connection pool.
  2. SessionLocal — a factory that produces Session objects.
  3. Base — the declarative base that all ORM models inherit from.
  4. get_db — the FastAPI dependency that opens/closes a session per
     request, used like: `db: Session = Depends(get_db)`.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator

from app.config import settings


# The engine is a connection pool. We create one per process.
# pool_pre_ping=True checks the connection is alive before using it —
# this protects us from the classic "stale connection" issue when the
# DB restarts or kicks idle connections.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)


# SessionLocal is a class-like factory. Calling SessionLocal() returns
# a new Session bound to the engine.
#   - autocommit=False: changes are pending until session.commit()
#   - autoflush=False: SQLAlchemy doesn't flush queries automatically
#                     (we control when SQL goes out)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# Every model class in app/models/ inherits from this Base. SQLAlchemy
# uses Base.metadata to know about all tables (used by Alembic).
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield one DB session per request, then close.

    The generator pattern (yield) ensures `db.close()` runs even if the
    endpoint raises an exception. FastAPI treats it like a context
    manager.

    Usage in endpoints:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
