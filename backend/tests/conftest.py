"""Shared pytest fixtures.

Tests run against an in-memory or test PostgreSQL DB (depending on the
DATABASE_URL env var when pytest runs). The fixtures here provide:

  - `db`: a SQLAlchemy session that's rolled back after each test
    (so tests don't leak state into each other).
  - `client`: a FastAPI TestClient backed by `db`.
  - `authenticated_client`: a client with a valid JWT for a test user.
  - `seeded_db`: db with synthetic asset+price data for engine tests.
"""

from datetime import date, timedelta
from decimal import Decimal
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.models import Asset, Price, User
from app.auth.password import hash_password
from app.auth.jwt import create_access_token


# Tests run against a separate test database. The TEST_DATABASE_URL env
# var lets CI inject a different connection string. Default points at a
# local Postgres instance ('postgres:test@localhost') configured in CI.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://portfolio:portfolio@db:5432/portfolio_builder_test",
)


@pytest.fixture(scope="session")
def engine():
    """One engine per test session. Tables created once, dropped at end."""
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine):
    """Per-test session. Rolls back at teardown so tests are isolated."""
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionFactory()
    yield session
    session.rollback()
    # Brutal cleanup: delete every row in dependency order.
    # Faster than truncating tables because Postgres can use the indexes.
    session.execute(__import__("sqlalchemy").text("DELETE FROM portfolios"))
    session.execute(__import__("sqlalchemy").text("DELETE FROM prices"))
    session.execute(__import__("sqlalchemy").text("DELETE FROM assets"))
    session.execute(__import__("sqlalchemy").text("DELETE FROM users"))
    session.commit()
    session.close()


@pytest.fixture
def client(db):
    """TestClient that uses the test db via dependency override."""
    def _get_test_db():
        yield db

    app.dependency_overrides[get_db] = _get_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db) -> User:
    """A pre-created user for auth tests."""
    user = User(
        email="alice@example.com",
        password_hash=hash_password("Password123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, test_user) -> TestClient:
    """TestClient with `Authorization: Bearer <token>` set for test_user."""
    token = create_access_token(test_user.id)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
def seeded_db(db) -> None:
    """Populate db with three synthetic assets and 1 year of fake prices.

    Prices are deterministic (seed=0) so engine tests are reproducible.
    """
    rng = np.random.default_rng(0)
    assets = [
        ("AAA", "Asset A", "equity"),
        ("BBB", "Asset B", "equity"),
        ("CCC", "Asset C", "bond"),
    ]
    for ticker, name, asset_class in assets:
        db.add(Asset(
            ticker=ticker, name=name,
            asset_class=asset_class, is_curated=True,
        ))
    db.commit()

    # Generate 1 year of synthetic daily prices for each asset.
    # Different drifts so MVO has interesting choices.
    drifts = {"AAA": 0.0008, "BBB": 0.0004, "CCC": 0.0001}
    vols = {"AAA": 0.012, "BBB": 0.010, "CCC": 0.003}
    start = date.today() - timedelta(days=400)

    for ticker in drifts:
        price = 100.0
        for i in range(252):
            dt = start + timedelta(days=i)
            r = rng.normal(drifts[ticker], vols[ticker])
            price = price * np.exp(r)
            db.add(Price(
                ticker=ticker,
                date=dt,
                close=Decimal(f"{price:.4f}"),
            ))
    db.commit()
