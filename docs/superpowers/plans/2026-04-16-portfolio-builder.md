# Portfolio Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that generates personalized stock portfolios for beginner investors using Markowitz optimization, ML prediction, and Monte Carlo simulation.

**Architecture:** FastAPI backend with a Portfolio Engine (ML Predictor → Markowitz Optimizer → Monte Carlo Simulator), React frontend with charts and forms, PostgreSQL for persistence, Redis + Celery for background jobs.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, yfinance, cvxpy, XGBoost, scikit-learn, numpy, scipy, Celery, Redis, React 18, TypeScript, Vite, Tailwind CSS, Recharts, Docker Compose.

---

## File Structure

### Backend
```
backend/
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, CORS, router includes
│   ├── config.py                  # Settings via pydantic-settings
│   ├── database.py                # SQLAlchemy engine, session
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt.py                 # create/verify tokens
│   │   ├── passwords.py           # hash/verify passwords
│   │   ├── dependencies.py        # get_current_user dependency
│   │   └── router.py              # /auth/register, /auth/login, /auth/refresh
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                # User model
│   │   ├── profile.py             # InvestmentProfile model
│   │   ├── portfolio.py           # Portfolio, PortfolioHolding models
│   │   ├── market_data.py         # MarketDataCache model
│   │   ├── snapshot.py            # PortfolioSnapshot model
│   │   └── country.py             # CountryRestriction model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                # RegisterRequest, LoginRequest, TokenResponse
│   │   ├── profile.py             # ProfileCreate, ProfileResponse
│   │   ├── portfolio.py           # PortfolioResponse, HoldingResponse
│   │   └── snapshot.py            # SnapshotResponse
│   ├── api/
│   │   ├── __init__.py
│   │   ├── profiles.py            # CRUD investment profiles
│   │   ├── portfolios.py          # generate, list, get, archive portfolios
│   │   └── snapshots.py           # portfolio performance history
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── universe.py            # stock filtering by country/sector/liquidity
│   │   ├── predictor.py           # XGBoost expected return predictor
│   │   ├── optimizer.py           # Markowitz portfolio optimization
│   │   ├── simulator.py           # Monte Carlo simulation
│   │   └── pipeline.py            # orchestrates universe→predictor→optimizer→simulator
│   ├── data/
│   │   ├── __init__.py
│   │   ├── market.py              # yfinance fetching + DB caching
│   │   └── country_data.py        # country→exchange mappings seed data
│   └── tasks/
│       ├── __init__.py
│       ├── celery_app.py          # Celery config
│       ├── market_update.py       # periodic market data refresh
│       └── snapshot_update.py     # periodic portfolio snapshot
└── tests/
    ├── conftest.py                # fixtures: test DB, client, auth headers
    ├── test_auth.py
    ├── test_profiles.py
    ├── test_portfolios.py
    ├── test_engine/
    │   ├── test_universe.py
    │   ├── test_predictor.py
    │   ├── test_optimizer.py
    │   ├── test_simulator.py
    │   └── test_pipeline.py
    └── test_data/
        └── test_market.py
```

### Frontend
```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx                    # Router setup
│   ├── api/
│   │   └── client.ts             # Axios instance + interceptors
│   ├── auth/
│   │   ├── AuthContext.tsx        # JWT context + provider
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   └── ProtectedRoute.tsx
│   ├── profile/
│   │   └── ProfileForm.tsx        # Investment questionnaire
│   ├── portfolio/
│   │   ├── PortfolioPage.tsx      # Main results page
│   │   ├── AllocationChart.tsx    # Pie chart
│   │   ├── BacktestChart.tsx      # Historical performance line chart
│   │   ├── MonteCarloChart.tsx    # Distribution fan chart
│   │   ├── RiskComparison.tsx     # Side-by-side risk level comparison
│   │   ├── HoldingsTable.tsx      # Stock list with allocations
│   │   └── DisclaimerBanner.tsx   # Prominent warning banner
│   ├── dashboard/
│   │   ├── DashboardPage.tsx      # List saved portfolios
│   │   └── PortfolioCard.tsx      # Summary card per portfolio
│   └── components/
│       ├── Layout.tsx             # Nav + main content wrapper
│       └── Spinner.tsx            # Loading indicator
```

### Infrastructure
```
docker-compose.yml
.env.example
```

---

## Task 1: Project Scaffolding & Docker

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/database.py`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-portfolio}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-portfolio}
      POSTGRES_DB: ${POSTGRES_DB:-portfolio_builder}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    env_file:
      - .env

  celery-worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env

  celery-beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat --loglevel=info
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env

volumes:
  pgdata:
```

- [ ] **Step 2: Create .env.example**

```env
DATABASE_URL=postgresql://portfolio:portfolio@db:5432/portfolio_builder
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

- [ ] **Step 3: Create backend/requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
alembic==1.13.0
psycopg2-binary==2.9.9
pydantic-settings==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
yfinance==0.2.40
numpy==1.26.4
scipy==1.14.0
cvxpy==1.5.0
scikit-learn==1.5.0
xgboost==2.1.0
celery[redis]==5.4.0
slowapi==0.1.9
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
```

- [ ] **Step 4: Create backend Dockerfile**

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Create backend/app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://portfolio:portfolio@localhost:5432/portfolio_builder"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 6: Create backend/app/database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 7: Create backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Portfolio Builder", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Create empty __init__.py files**

Create empty `__init__.py` in: `backend/app/`, `backend/app/auth/`, `backend/app/models/`, `backend/app/schemas/`, `backend/app/api/`, `backend/app/engine/`, `backend/app/data/`, `backend/app/tasks/`, `backend/tests/`, `backend/tests/test_engine/`, `backend/tests/test_data/`.

- [ ] **Step 9: Verify Docker starts**

Run: `cd /Users/roeykarif/Portfolio-Builder && docker compose up --build -d`
Expected: All services start. `curl http://localhost:8000/health` returns `{"status":"ok"}`.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with Docker, FastAPI, PostgreSQL, Redis"
```

---

## Task 2: Database Models & Migrations

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/profile.py`
- Create: `backend/app/models/portfolio.py`
- Create: `backend/app/models/market_data.py`
- Create: `backend/app/models/snapshot.py`
- Create: `backend/app/models/country.py`
- Create: `backend/app/models/__init__.py` (re-exports)
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: Create backend/app/models/user.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profiles = relationship("InvestmentProfile", back_populates="user")
    portfolios = relationship("Portfolio", back_populates="user")
```

- [ ] **Step 2: Create backend/app/models/profile.py**

```python
import uuid
from sqlalchemy import String, Integer, Numeric, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvestmentProfile(Base):
    __tablename__ = "investment_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    risk_level: Mapped[int] = mapped_column(Integer)  # 1-5
    investment_horizon: Mapped[str] = mapped_column(String(20))
    available_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    target_return: Mapped[float] = mapped_column(Numeric(5, 2))
    preferred_sectors: Mapped[list] = mapped_column(JSON, default=list)
    include_tickers: Mapped[list] = mapped_column(JSON, default=list)
    exclude_tickers: Mapped[list] = mapped_column(JSON, default=list)

    user = relationship("User", back_populates="profiles")
    portfolios = relationship("Portfolio", back_populates="profile")
```

- [ ] **Step 3: Create backend/app/models/portfolio.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investment_profiles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="active")
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2))
    expected_return_low: Mapped[float] = mapped_column(Numeric(5, 2))
    expected_return_high: Mapped[float] = mapped_column(Numeric(5, 2))
    total_value: Mapped[float] = mapped_column(Numeric(14, 2))

    user = relationship("User", back_populates="portfolios")
    profile = relationship("InvestmentProfile", back_populates="portfolios")
    holdings = relationship("PortfolioHolding", back_populates="portfolio")
    snapshots = relationship("PortfolioSnapshot", back_populates="portfolio")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"))
    ticker: Mapped[str] = mapped_column(String(10))
    company_name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(100))
    allocation_pct: Mapped[float] = mapped_column(Numeric(5, 2))
    expected_return: Mapped[float] = mapped_column(Numeric(5, 2))

    portfolio = relationship("Portfolio", back_populates="holdings")
```

- [ ] **Step 4: Create backend/app/models/market_data.py**

```python
from datetime import date, datetime

from sqlalchemy import String, Numeric, BigInteger, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketDataCache(Base):
    __tablename__ = "market_data_cache"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Numeric(12, 4))
    close: Mapped[float] = mapped_column(Numeric(12, 4))
    high: Mapped[float] = mapped_column(Numeric(12, 4))
    low: Mapped[float] = mapped_column(Numeric(12, 4))
    volume: Mapped[int] = mapped_column(BigInteger)
    pe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    pb_ratio: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 5: Create backend/app/models/snapshot.py**

```python
import uuid
from datetime import date

from sqlalchemy import Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"))
    date: Mapped[date] = mapped_column(Date)
    total_value: Mapped[float] = mapped_column(Numeric(14, 2))
    daily_return: Mapped[float] = mapped_column(Numeric(8, 4))

    portfolio = relationship("Portfolio", back_populates="snapshots")
```

- [ ] **Step 6: Create backend/app/models/country.py**

```python
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CountryRestriction(Base):
    __tablename__ = "country_restrictions"

    country_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    allowed_exchanges: Mapped[list] = mapped_column(JSON)
```

- [ ] **Step 7: Update backend/app/models/__init__.py with re-exports**

```python
from app.models.user import User
from app.models.profile import InvestmentProfile
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.market_data import MarketDataCache
from app.models.snapshot import PortfolioSnapshot
from app.models.country import CountryRestriction

__all__ = [
    "User",
    "InvestmentProfile",
    "Portfolio",
    "PortfolioHolding",
    "MarketDataCache",
    "PortfolioSnapshot",
    "CountryRestriction",
]
```

- [ ] **Step 8: Initialize Alembic**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && alembic init alembic`

Then edit `backend/alembic/env.py` — replace the target_metadata line:

```python
from app.database import Base
from app.models import *  # noqa: F401, F403

target_metadata = Base.metadata
```

Edit `backend/alembic.ini` — set sqlalchemy.url:
```ini
sqlalchemy.url = postgresql://portfolio:portfolio@localhost:5432/portfolio_builder
```

- [ ] **Step 9: Generate and run first migration**

Run:
```bash
cd /Users/roeykarif/Portfolio-Builder/backend
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Expected: Migration created in `alembic/versions/`, all 7 tables created in DB.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: database models and initial migration for all 7 tables"
```

---

## Task 3: Authentication System

**Files:**
- Create: `backend/app/auth/passwords.py`
- Create: `backend/app/auth/jwt.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/auth/router.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`
- Modify: `backend/app/main.py` (add auth router)

- [ ] **Step 1: Write auth tests**

Create `backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql://portfolio:portfolio@localhost:5432/portfolio_builder_test"
engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "testpassword123",
        "country": "US",
    })
    resp = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

Create `backend/tests/test_auth.py`:
```python
def test_register_success(client):
    resp = client.post("/auth/register", json={
        "email": "new@example.com",
        "password": "securepass123",
        "country": "US",
    })
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@example.com"


def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "pass123", "country": "US"}
    client.post("/auth/register", json=payload)
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409


def test_login_success(client):
    client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "pass123",
        "country": "US",
    })
    resp = client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "pass123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "email": "wrong@example.com",
        "password": "pass123",
        "country": "US",
    })
    resp = client.post("/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


def test_refresh_token(client):
    client.post("/auth/register", json={
        "email": "refresh@example.com",
        "password": "pass123",
        "country": "US",
    })
    login_resp = client.post("/auth/login", json={
        "email": "refresh@example.com",
        "password": "pass123",
    })
    refresh_token = login_resp.json()["refresh_token"]
    resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_auth.py -v`
Expected: FAIL — routes don't exist yet.

- [ ] **Step 3: Create backend/app/auth/passwords.py**

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

- [ ] **Step 4: Create backend/app/auth/jwt.py**

```python
from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "access"}, settings.secret_key, ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "refresh"}, settings.secret_key, ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
```

- [ ] **Step 5: Create backend/app/auth/dependencies.py**

```python
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token
from app.database import get_db
from app.models.user import User

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == uuid.UUID(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 6: Create backend/app/schemas/auth.py**

```python
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    country: str


class RegisterResponse(BaseModel):
    id: str
    email: str
    country: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 7: Create backend/app/auth/router.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.passwords import hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=req.email, password_hash=hash_password(req.password), country=req.country)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RegisterResponse(id=str(user.id), email=user.email, country=user.country)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user_id = payload["sub"]
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )
```

- [ ] **Step 8: Add auth router to main.py**

Update `backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router

app = FastAPI(title="Portfolio Builder", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_auth.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: JWT authentication with register, login, refresh endpoints"
```

---

## Task 4: Investment Profile API

**Files:**
- Create: `backend/app/schemas/profile.py`
- Create: `backend/app/api/profiles.py`
- Create: `backend/tests/test_profiles.py`
- Modify: `backend/app/main.py` (add profiles router)

- [ ] **Step 1: Write profile tests**

Create `backend/tests/test_profiles.py`:
```python
PROFILE_PAYLOAD = {
    "risk_level": 3,
    "investment_horizon": "3-5y",
    "available_amount": 50000.00,
    "target_return": 12.0,
    "preferred_sectors": ["Technology", "Healthcare"],
    "include_tickers": ["AAPL"],
    "exclude_tickers": ["META"],
}


def test_create_profile(client, auth_headers):
    resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["risk_level"] == 3
    assert data["available_amount"] == 50000.00


def test_list_profiles(client, auth_headers):
    client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    resp = client.get("/profiles", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_profile(client, auth_headers):
    create_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = create_resp.json()["id"]
    resp = client.get(f"/profiles/{profile_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == profile_id


def test_create_profile_unauthorized(client):
    resp = client.post("/profiles", json=PROFILE_PAYLOAD)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_profiles.py -v`
Expected: FAIL — routes don't exist yet.

- [ ] **Step 3: Create backend/app/schemas/profile.py**

```python
import uuid
from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    risk_level: int = Field(ge=1, le=5)
    investment_horizon: str
    available_amount: float = Field(gt=0)
    target_return: float = Field(gt=0, le=100)
    preferred_sectors: list[str] = []
    include_tickers: list[str] = []
    exclude_tickers: list[str] = []


class ProfileResponse(BaseModel):
    id: str
    risk_level: int
    investment_horizon: str
    available_amount: float
    target_return: float
    preferred_sectors: list[str]
    include_tickers: list[str]
    exclude_tickers: list[str]

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create backend/app/api/profiles.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.profile import InvestmentProfile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileResponse

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_response(profile: InvestmentProfile) -> ProfileResponse:
    return ProfileResponse(
        id=str(profile.id),
        risk_level=profile.risk_level,
        investment_horizon=profile.investment_horizon,
        available_amount=float(profile.available_amount),
        target_return=float(profile.target_return),
        preferred_sectors=profile.preferred_sectors,
        include_tickers=profile.include_tickers,
        exclude_tickers=profile.exclude_tickers,
    )


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    req: ProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = InvestmentProfile(user_id=user.id, **req.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_response(profile)


@router.get("", response_model=list[ProfileResponse])
def list_profiles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profiles = db.query(InvestmentProfile).filter(InvestmentProfile.user_id == user.id).all()
    return [_to_response(p) for p in profiles]


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(InvestmentProfile).filter(
        InvestmentProfile.id == profile_id,
        InvestmentProfile.user_id == user.id,
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return _to_response(profile)
```

- [ ] **Step 5: Add profiles router to main.py**

Add to `backend/app/main.py`:
```python
from app.api.profiles import router as profiles_router
app.include_router(profiles_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_profiles.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: investment profile CRUD API with auth protection"
```

---

## Task 5: Market Data Layer

**Files:**
- Create: `backend/app/data/market.py`
- Create: `backend/app/data/country_data.py`
- Create: `backend/tests/test_data/test_market.py`

- [ ] **Step 1: Write market data tests**

Create `backend/tests/test_data/test_market.py`:
```python
from unittest.mock import patch, MagicMock
from datetime import date

import pandas as pd

from app.data.market import fetch_stock_data, get_cached_or_fetch


def _mock_yf_download(tickers, start, end, **kwargs):
    """Return a DataFrame shaped like yfinance output."""
    dates = pd.date_range(start, end, freq="B")[:5]
    data = {
        "Open": [100.0] * 5,
        "High": [105.0] * 5,
        "Low": [95.0] * 5,
        "Close": [102.0] * 5,
        "Volume": [1000000] * 5,
    }
    return pd.DataFrame(data, index=dates)


@patch("app.data.market.yf.download", side_effect=_mock_yf_download)
def test_fetch_stock_data(mock_download):
    df = fetch_stock_data("AAPL", start="2024-01-01", end="2024-01-10")
    assert len(df) == 5
    assert "Close" in df.columns
    mock_download.assert_called_once()


@patch("app.data.market.yf.download", side_effect=_mock_yf_download)
def test_get_cached_or_fetch_calls_yfinance_on_miss(mock_download, db):
    df = get_cached_or_fetch(db, "AAPL", start="2024-01-01", end="2024-01-10")
    assert len(df) == 5
    mock_download.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_data/test_market.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create backend/app/data/market.py**

```python
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models.market_data import MarketDataCache


def fetch_stock_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch historical OHLCV data from yfinance."""
    df = yf.download(ticker, start=start, end=end, progress=False)
    return df


def get_cached_or_fetch(db: Session, ticker: str, start: str, end: str) -> pd.DataFrame:
    """Return market data from cache if fresh, otherwise fetch and cache."""
    cached = (
        db.query(MarketDataCache)
        .filter(
            MarketDataCache.ticker == ticker,
            MarketDataCache.date >= date.fromisoformat(start),
            MarketDataCache.date <= date.fromisoformat(end),
        )
        .all()
    )

    if cached:
        latest = max(c.last_updated for c in cached)
        if datetime.utcnow() - latest < timedelta(hours=24):
            return pd.DataFrame(
                [{"Date": c.date, "Open": float(c.open), "High": float(c.high),
                  "Low": float(c.low), "Close": float(c.close), "Volume": c.volume}
                 for c in cached]
            ).set_index("Date")

    df = fetch_stock_data(ticker, start=start, end=end)
    _save_to_cache(db, ticker, df)
    return df


def _save_to_cache(db: Session, ticker: str, df: pd.DataFrame) -> None:
    """Upsert market data rows into cache."""
    for idx, row in df.iterrows():
        row_date = idx.date() if hasattr(idx, "date") else idx
        existing = (
            db.query(MarketDataCache)
            .filter(MarketDataCache.ticker == ticker, MarketDataCache.date == row_date)
            .first()
        )
        if existing:
            existing.open = float(row["Open"])
            existing.high = float(row["High"])
            existing.low = float(row["Low"])
            existing.close = float(row["Close"])
            existing.volume = int(row["Volume"])
            existing.last_updated = datetime.utcnow()
        else:
            db.add(MarketDataCache(
                ticker=ticker, date=row_date,
                open=float(row["Open"]), high=float(row["High"]),
                low=float(row["Low"]), close=float(row["Close"]),
                volume=int(row["Volume"]), last_updated=datetime.utcnow(),
            ))
    db.commit()


def fetch_stock_info(ticker: str) -> dict:
    """Fetch fundamental info (P/E, P/B, dividend yield, sector, name)."""
    stock = yf.Ticker(ticker)
    info = stock.info
    return {
        "company_name": info.get("shortName", ticker),
        "sector": info.get("sector", "Unknown"),
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "market_cap": info.get("marketCap"),
        "average_volume": info.get("averageVolume"),
        "exchange": info.get("exchange", ""),
    }
```

- [ ] **Step 4: Create backend/app/data/country_data.py**

```python
"""Country-to-exchange mappings for filtering available stocks."""

COUNTRY_EXCHANGES: dict[str, list[str]] = {
    "US": ["NYSE", "NMS", "NASDAQ", "AMEX", "NYQ", "NAS", "NGM", "NCM", "PCX"],
    "IL": ["TLV", "TAE"],
    "GB": ["LSE", "LON"],
    "DE": ["FRA", "GER", "XETRA"],
    "FR": ["PAR", "EPA"],
    "JP": ["JPX", "TYO"],
    "CN": ["SHA", "SHE"],
    "HK": ["HKG"],
    "CA": ["TSX", "TOR"],
    "AU": ["ASX"],
}


def get_allowed_exchanges(country_code: str) -> list[str]:
    """Return list of allowed exchange codes for a country. Defaults to US exchanges."""
    return COUNTRY_EXCHANGES.get(country_code.upper(), COUNTRY_EXCHANGES["US"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_data/test_market.py -v`
Expected: All 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: market data layer with yfinance fetching and DB caching"
```

---

## Task 6: Portfolio Engine — Universe Selection

**Files:**
- Create: `backend/app/engine/universe.py`
- Create: `backend/tests/test_engine/test_universe.py`

- [ ] **Step 1: Write universe selection tests**

Create `backend/tests/test_engine/test_universe.py`:
```python
from unittest.mock import patch

from app.engine.universe import select_universe


def _mock_fetch_info(ticker: str) -> dict:
    stock_db = {
        "AAPL": {"company_name": "Apple", "sector": "Technology", "exchange": "NMS", "average_volume": 50_000_000},
        "MSFT": {"company_name": "Microsoft", "sector": "Technology", "exchange": "NMS", "average_volume": 30_000_000},
        "JNJ": {"company_name": "Johnson & Johnson", "sector": "Healthcare", "exchange": "NYSE", "average_volume": 8_000_000},
        "XOM": {"company_name": "Exxon Mobil", "sector": "Energy", "exchange": "NYSE", "average_volume": 15_000_000},
        "TEVA": {"company_name": "Teva", "sector": "Healthcare", "exchange": "TLV", "average_volume": 5_000_000},
        "TINY": {"company_name": "TinyStock", "sector": "Technology", "exchange": "NMS", "average_volume": 1_000},
    }
    return stock_db.get(ticker, {"company_name": ticker, "sector": "Unknown", "exchange": "UNKNOWN", "average_volume": 0})


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers", return_value=["AAPL", "MSFT", "JNJ", "XOM", "TEVA", "TINY"])
def test_filter_by_country_us(mock_tickers, mock_info):
    result = select_universe(
        country="US",
        sectors=["Technology", "Healthcare"],
        include_tickers=[],
        exclude_tickers=[],
    )
    tickers = [s["ticker"] for s in result]
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "JNJ" in tickers
    assert "TEVA" not in tickers  # TLV exchange, not available for US
    assert "TINY" not in tickers  # low volume


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers", return_value=["AAPL", "MSFT", "JNJ", "XOM", "TEVA", "TINY"])
def test_include_exclude_tickers(mock_tickers, mock_info):
    result = select_universe(
        country="US",
        sectors=["Technology"],
        include_tickers=["XOM"],
        exclude_tickers=["MSFT"],
    )
    tickers = [s["ticker"] for s in result]
    assert "XOM" in tickers  # included even though not in Technology sector
    assert "MSFT" not in tickers  # excluded


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers", return_value=["AAPL", "MSFT", "JNJ"])
def test_filter_by_sector(mock_tickers, mock_info):
    result = select_universe(
        country="US",
        sectors=["Healthcare"],
        include_tickers=[],
        exclude_tickers=[],
    )
    tickers = [s["ticker"] for s in result]
    assert "JNJ" in tickers
    assert "AAPL" not in tickers  # Technology, not Healthcare
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_universe.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create backend/app/engine/universe.py**

```python
from app.data.country_data import get_allowed_exchanges
from app.data.market import fetch_stock_info

VOLUME_THRESHOLD = 100_000  # minimum average daily volume


def select_universe(
    country: str,
    sectors: list[str],
    include_tickers: list[str],
    exclude_tickers: list[str],
) -> list[dict]:
    """
    Select stocks available to the user based on country, sectors, and preferences.
    Returns list of dicts: {"ticker", "company_name", "sector", "exchange"}.
    """
    allowed_exchanges = get_allowed_exchanges(country)

    # Get candidate tickers for requested sectors
    candidates = set(_get_sector_tickers(sectors))

    # Add explicitly included tickers
    candidates.update(include_tickers)

    # Remove explicitly excluded tickers
    candidates -= set(exclude_tickers)

    # Fetch info and filter
    result = []
    for ticker in candidates:
        info = fetch_stock_info(ticker)

        # Filter by exchange
        if info.get("exchange", "") not in allowed_exchanges:
            # Still allow if user explicitly included it
            if ticker not in include_tickers:
                continue

        # Filter by sector (unless explicitly included)
        if ticker not in include_tickers and info.get("sector") not in sectors:
            continue

        # Filter by liquidity
        if info.get("average_volume", 0) < VOLUME_THRESHOLD:
            if ticker not in include_tickers:
                continue

        result.append({
            "ticker": ticker,
            "company_name": info.get("company_name", ticker),
            "sector": info.get("sector", "Unknown"),
            "exchange": info.get("exchange", ""),
        })

    return result


def _get_sector_tickers(sectors: list[str]) -> list[str]:
    """
    Get a list of tickers for given sectors.
    Uses yfinance screener or a curated list of S&P 500 / major index components.
    """
    import yfinance as yf

    sector_map = {
        "Technology": "technology",
        "Healthcare": "healthcare",
        "Energy": "energy",
        "Finance": "financial-services",
        "Consumer": "consumer-cyclical",
        "Real Estate": "real-estate",
        "Industrial": "industrials",
    }

    tickers = []
    for sector in sectors:
        yf_sector = sector_map.get(sector)
        if not yf_sector:
            continue
        try:
            screener = yf.Sector(yf_sector)
            top = screener.top_companies
            if top is not None and not top.empty:
                tickers.extend(top.index.tolist()[:30])  # top 30 per sector
        except Exception:
            continue

    return list(set(tickers))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_universe.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: universe selection — filter stocks by country, sector, liquidity"
```

---

## Task 7: Portfolio Engine — ML Predictor

**Files:**
- Create: `backend/app/engine/predictor.py`
- Create: `backend/tests/test_engine/test_predictor.py`

- [ ] **Step 1: Write predictor tests**

Create `backend/tests/test_engine/test_predictor.py`:
```python
import numpy as np
import pandas as pd
from unittest.mock import patch

from app.engine.predictor import build_features, predict_returns


def _make_price_series(n_days=252, base_price=100.0, ticker="AAPL"):
    """Generate synthetic daily price data."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
    returns = np.random.normal(0.0005, 0.02, n_days)
    prices = base_price * np.cumprod(1 + returns)
    return pd.DataFrame({
        "Close": prices,
        "Volume": np.random.randint(1_000_000, 10_000_000, n_days),
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Open": prices * 1.005,
    }, index=dates)


def test_build_features():
    df = _make_price_series()
    features = build_features(df)
    assert "return_5d" in features.columns
    assert "return_21d" in features.columns
    assert "volatility_21d" in features.columns
    assert "momentum_63d" in features.columns
    assert "sma_50_ratio" in features.columns
    assert len(features) > 0
    assert not features.isnull().all().any()


@patch("app.engine.predictor.fetch_stock_data")
@patch("app.engine.predictor.fetch_stock_info")
def test_predict_returns(mock_info, mock_fetch):
    mock_info.return_value = {"pe_ratio": 25.0, "pb_ratio": 8.0, "dividend_yield": 0.005}
    mock_fetch.return_value = _make_price_series()

    stocks = [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "exchange": "NMS"},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "exchange": "NMS"},
    ]
    result = predict_returns(stocks, db=None)

    assert len(result) == 2
    for stock in result:
        assert "expected_return" in stock
        assert isinstance(stock["expected_return"], float)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_predictor.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create backend/app/engine/predictor.py**

```python
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.data.market import fetch_stock_data, fetch_stock_info


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build ML features from OHLCV price data."""
    features = pd.DataFrame(index=df.index)

    # Returns over various windows
    features["return_5d"] = df["Close"].pct_change(5)
    features["return_21d"] = df["Close"].pct_change(21)
    features["return_63d"] = df["Close"].pct_change(63)

    # Volatility
    features["volatility_21d"] = df["Close"].pct_change().rolling(21).std()
    features["volatility_63d"] = df["Close"].pct_change().rolling(63).std()

    # Momentum
    features["momentum_63d"] = df["Close"] / df["Close"].shift(63) - 1

    # Moving average ratios
    features["sma_50_ratio"] = df["Close"] / df["Close"].rolling(50).mean()
    features["sma_200_ratio"] = df["Close"] / df["Close"].rolling(200).mean()

    # Volume trend
    features["volume_ratio_20d"] = df["Volume"] / df["Volume"].rolling(20).mean()

    return features.dropna()


def predict_returns(stocks: list[dict], db) -> list[dict]:
    """
    Predict expected annual returns for a list of stocks.
    Uses XGBoost trained on each stock's own historical patterns.
    """
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")

    results = []
    for stock in stocks:
        ticker = stock["ticker"]
        try:
            df = fetch_stock_data(ticker, start=start_date, end=end_date)
            if len(df) < 252:  # need at least 1 year of data
                stock["expected_return"] = 0.0
                results.append(stock)
                continue

            info = fetch_stock_info(ticker)
            features = build_features(df)

            # Target: forward 21-day return (annualized)
            forward_return = df["Close"].pct_change(21).shift(-21)
            forward_return = forward_return.reindex(features.index).dropna()
            features = features.loc[forward_return.index]

            # Add fundamental features
            features["pe_ratio"] = info.get("pe_ratio") or 0.0
            features["pb_ratio"] = info.get("pb_ratio") or 0.0
            features["dividend_yield"] = info.get("dividend_yield") or 0.0

            # Train on all but last 21 days, predict from latest features
            X = features.values
            y = forward_return.values

            if len(X) < 50:
                stock["expected_return"] = 0.0
                results.append(stock)
                continue

            model = XGBRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.05,
                random_state=42,
            )
            model.fit(X[:-21], y[:-21])

            # Predict using latest available features
            latest_features = X[-1:].copy()
            predicted_21d_return = float(model.predict(latest_features)[0])

            # Annualize: (1 + 21d_return)^(252/21) - 1
            annual_return = (1 + predicted_21d_return) ** (252 / 21) - 1
            stock["expected_return"] = round(annual_return, 4)

        except Exception:
            stock["expected_return"] = 0.0

        results.append(stock)

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_predictor.py -v`
Expected: All 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: XGBoost ML predictor for expected stock returns"
```

---

## Task 8: Portfolio Engine — Markowitz Optimizer

**Files:**
- Create: `backend/app/engine/optimizer.py`
- Create: `backend/tests/test_engine/test_optimizer.py`

- [ ] **Step 1: Write optimizer tests**

Create `backend/tests/test_engine/test_optimizer.py`:
```python
import numpy as np
from app.engine.optimizer import optimize_portfolio


def test_basic_optimization():
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09])
    # Covariance matrix (symmetric positive definite)
    cov_matrix = np.array([
        [0.04, 0.006, 0.002, 0.01, 0.003],
        [0.006, 0.03, 0.004, 0.008, 0.002],
        [0.002, 0.004, 0.02, 0.003, 0.001],
        [0.01, 0.008, 0.003, 0.05, 0.005],
        [0.003, 0.002, 0.001, 0.005, 0.025],
    ])
    tickers = ["AAPL", "MSFT", "JNJ", "TSLA", "PG"]

    result = optimize_portfolio(
        tickers=tickers,
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        risk_level=3,
        target_return=0.10,
    )

    assert len(result["weights"]) == 5
    assert abs(sum(result["weights"].values()) - 1.0) < 0.01  # weights sum to ~1
    assert all(w >= 0 for w in result["weights"].values())  # no short selling
    assert all(w <= 0.30 for w in result["weights"].values())  # max 30% per stock
    assert "portfolio_return" in result
    assert "portfolio_volatility" in result


def test_minimum_stocks_constraint():
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09, 0.11, 0.07])
    cov_matrix = np.eye(7) * 0.03
    tickers = ["A", "B", "C", "D", "E", "F", "G"]

    result = optimize_portfolio(
        tickers=tickers,
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        risk_level=3,
        target_return=0.10,
    )

    non_zero = sum(1 for w in result["weights"].values() if w > 0.01)
    assert non_zero >= 5


def test_low_risk_reduces_volatility():
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09])
    cov_matrix = np.array([
        [0.04, 0.006, 0.002, 0.01, 0.003],
        [0.006, 0.03, 0.004, 0.008, 0.002],
        [0.002, 0.004, 0.02, 0.003, 0.001],
        [0.01, 0.008, 0.003, 0.05, 0.005],
        [0.003, 0.002, 0.001, 0.005, 0.025],
    ])
    tickers = ["AAPL", "MSFT", "JNJ", "TSLA", "PG"]

    low_risk = optimize_portfolio(tickers, expected_returns, cov_matrix, risk_level=1, target_return=0.08)
    high_risk = optimize_portfolio(tickers, expected_returns, cov_matrix, risk_level=5, target_return=0.12)

    assert low_risk["portfolio_volatility"] <= high_risk["portfolio_volatility"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_optimizer.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create backend/app/engine/optimizer.py**

```python
import numpy as np
import cvxpy as cp

# Risk level → max annual volatility
RISK_VOLATILITY_CAP = {
    1: 0.08,   # very conservative
    2: 0.12,   # conservative
    3: 0.18,   # balanced
    4: 0.25,   # aggressive
    5: 0.35,   # very aggressive
}

MAX_SINGLE_WEIGHT = 0.30
MIN_STOCKS = 5
MIN_WEIGHT_THRESHOLD = 0.02  # below this, set to 0


def optimize_portfolio(
    tickers: list[str],
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_level: int,
    target_return: float,
) -> dict:
    """
    Markowitz mean-variance optimization.
    Returns optimal weights, expected return, and volatility.
    """
    n = len(tickers)
    max_vol = RISK_VOLATILITY_CAP.get(risk_level, 0.18)

    weights = cp.Variable(n)
    ret = expected_returns @ weights
    risk = cp.quad_form(weights, cov_matrix)

    constraints = [
        cp.sum(weights) == 1,          # fully invested
        weights >= 0,                   # no short selling
        weights <= MAX_SINGLE_WEIGHT,   # diversification cap
    ]

    # Add volatility cap based on risk level
    constraints.append(risk <= max_vol ** 2)

    # Objective: maximize return (within risk constraints)
    objective = cp.Maximize(ret)

    problem = cp.Problem(objective, constraints)

    try:
        problem.solve(solver=cp.SCS)
    except cp.SolverError:
        problem.solve(solver=cp.ECOS)

    if problem.status not in ("optimal", "optimal_inaccurate"):
        # Fallback: equal-weight portfolio
        equal_w = np.ones(n) / n
        return {
            "weights": {t: round(float(w), 4) for t, w in zip(tickers, equal_w)},
            "portfolio_return": float(expected_returns @ equal_w),
            "portfolio_volatility": float(np.sqrt(equal_w @ cov_matrix @ equal_w)),
            "status": "fallback_equal_weight",
        }

    raw_weights = weights.value
    # Clean up tiny weights
    clean_weights = np.where(raw_weights < MIN_WEIGHT_THRESHOLD, 0, raw_weights)
    # Re-normalize
    if clean_weights.sum() > 0:
        clean_weights = clean_weights / clean_weights.sum()
    else:
        clean_weights = np.ones(n) / n

    port_return = float(expected_returns @ clean_weights)
    port_vol = float(np.sqrt(clean_weights @ cov_matrix @ clean_weights))

    return {
        "weights": {t: round(float(w), 4) for t, w in zip(tickers, clean_weights)},
        "portfolio_return": round(port_return, 4),
        "portfolio_volatility": round(port_vol, 4),
        "status": "optimal",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_optimizer.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: Markowitz portfolio optimizer with cvxpy"
```

---

## Task 9: Portfolio Engine — Monte Carlo Simulator

**Files:**
- Create: `backend/app/engine/simulator.py`
- Create: `backend/tests/test_engine/test_simulator.py`

- [ ] **Step 1: Write simulator tests**

Create `backend/tests/test_engine/test_simulator.py`:
```python
import numpy as np
from app.engine.simulator import run_monte_carlo


def test_monte_carlo_output_shape():
    weights = np.array([0.3, 0.3, 0.2, 0.2])
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15])
    cov_matrix = np.eye(4) * 0.03

    result = run_monte_carlo(
        weights=weights,
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        initial_value=50000,
        horizon_years=3,
        n_simulations=1000,
    )

    assert "percentile_10" in result
    assert "percentile_50" in result
    assert "percentile_90" in result
    assert "return_low" in result
    assert "return_high" in result
    assert result["percentile_10"] < result["percentile_50"] < result["percentile_90"]


def test_monte_carlo_reasonable_values():
    weights = np.array([0.5, 0.5])
    expected_returns = np.array([0.10, 0.10])
    cov_matrix = np.array([[0.04, 0.01], [0.01, 0.04]])

    result = run_monte_carlo(
        weights=weights,
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        initial_value=100000,
        horizon_years=5,
        n_simulations=10000,
    )

    # After 5 years at ~10% expected, median should be around 150k-170k
    assert 80_000 < result["percentile_50"] < 300_000
    # Low end shouldn't be negative
    assert result["percentile_10"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_simulator.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create backend/app/engine/simulator.py**

```python
import numpy as np


def run_monte_carlo(
    weights: np.ndarray,
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    initial_value: float,
    horizon_years: float,
    n_simulations: int = 10_000,
) -> dict:
    """
    Run Monte Carlo simulation for a portfolio.
    Uses geometric Brownian motion with correlated returns.

    Returns percentile values and return ranges.
    """
    trading_days = int(252 * horizon_years)

    # Portfolio expected daily return and volatility
    port_annual_return = float(weights @ expected_returns)
    port_annual_vol = float(np.sqrt(weights @ cov_matrix @ weights))
    daily_return = port_annual_return / 252
    daily_vol = port_annual_vol / np.sqrt(252)

    # Simulate paths
    np.random.seed(None)  # truly random each run
    random_returns = np.random.normal(daily_return, daily_vol, (n_simulations, trading_days))

    # Cumulative returns → final portfolio values
    cumulative = np.cumprod(1 + random_returns, axis=1)
    final_values = initial_value * cumulative[:, -1]

    p10 = float(np.percentile(final_values, 10))
    p50 = float(np.percentile(final_values, 50))
    p90 = float(np.percentile(final_values, 90))

    # Annualized returns for the range
    return_low = (p10 / initial_value) ** (1 / horizon_years) - 1
    return_high = (p90 / initial_value) ** (1 / horizon_years) - 1

    return {
        "percentile_10": round(p10, 2),
        "percentile_50": round(p50, 2),
        "percentile_90": round(p90, 2),
        "return_low": round(return_low, 4),
        "return_high": round(return_high, 4),
        "initial_value": initial_value,
        "horizon_years": horizon_years,
        "n_simulations": n_simulations,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_simulator.py -v`
Expected: All 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: Monte Carlo simulator with configurable scenarios"
```

---

## Task 10: Portfolio Engine — Pipeline (Orchestrator)

**Files:**
- Create: `backend/app/engine/pipeline.py`
- Create: `backend/tests/test_engine/test_pipeline.py`

- [ ] **Step 1: Write pipeline tests**

Create `backend/tests/test_engine/test_pipeline.py`:
```python
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd

from app.engine.pipeline import generate_portfolio


def _mock_select_universe(**kwargs):
    return [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "exchange": "NMS"},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "exchange": "NMS"},
        {"ticker": "JNJ", "company_name": "J&J", "sector": "Healthcare", "exchange": "NYSE"},
        {"ticker": "PG", "company_name": "P&G", "sector": "Consumer", "exchange": "NYSE"},
        {"ticker": "XOM", "company_name": "Exxon", "sector": "Energy", "exchange": "NYSE"},
    ]


def _mock_predict_returns(stocks, db):
    for s in stocks:
        s["expected_return"] = np.random.uniform(0.05, 0.15)
    return stocks


def _mock_fetch_data(ticker, start, end):
    np.random.seed(hash(ticker) % 2**31)
    n = 252
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(0.0004, 0.02, n))
    return pd.DataFrame({"Close": prices}, index=dates)


@patch("app.engine.pipeline.fetch_stock_data", side_effect=_mock_fetch_data)
@patch("app.engine.pipeline.predict_returns", side_effect=_mock_predict_returns)
@patch("app.engine.pipeline.select_universe", side_effect=_mock_select_universe)
def test_generate_portfolio(mock_universe, mock_predict, mock_fetch):
    result = generate_portfolio(
        country="US",
        risk_level=3,
        investment_horizon="3-5y",
        available_amount=50000,
        target_return=0.10,
        preferred_sectors=["Technology", "Healthcare"],
        include_tickers=[],
        exclude_tickers=[],
        db=None,
    )

    assert "holdings" in result
    assert len(result["holdings"]) >= 1
    assert "risk_score" in result
    assert "expected_return_low" in result
    assert "expected_return_high" in result
    assert "simulation" in result

    total_alloc = sum(h["allocation_pct"] for h in result["holdings"])
    assert abs(total_alloc - 100.0) < 1.0  # allocations sum to ~100%
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_pipeline.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create backend/app/engine/pipeline.py**

```python
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.data.market import fetch_stock_data
from app.engine.universe import select_universe
from app.engine.predictor import predict_returns
from app.engine.optimizer import optimize_portfolio
from app.engine.simulator import run_monte_carlo

HORIZON_YEARS = {
    "6m": 0.5,
    "1-3y": 2.0,
    "3-5y": 4.0,
    "5y+": 7.0,
}


def generate_portfolio(
    country: str,
    risk_level: int,
    investment_horizon: str,
    available_amount: float,
    target_return: float,
    preferred_sectors: list[str],
    include_tickers: list[str],
    exclude_tickers: list[str],
    db,
) -> dict:
    """
    Full pipeline: universe → predict → optimize → simulate.
    Returns portfolio holdings, risk metrics, and simulation results.
    """
    # Stage 1: Universe Selection
    stocks = select_universe(
        country=country,
        sectors=preferred_sectors,
        include_tickers=include_tickers,
        exclude_tickers=exclude_tickers,
    )

    if len(stocks) < 5:
        return {"error": "Not enough stocks found. Try broadening your sector selection."}

    # Stage 2: ML Prediction
    stocks = predict_returns(stocks, db=db)

    # Build covariance matrix from historical data
    tickers = [s["ticker"] for s in stocks]
    expected_rets = np.array([s["expected_return"] for s in stocks])

    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=2 * 365)).strftime("%Y-%m-%d")

    price_data = {}
    for ticker in tickers:
        try:
            df = fetch_stock_data(ticker, start=start_date, end=end_date)
            price_data[ticker] = df["Close"]
        except Exception:
            continue

    # Remove stocks without price data
    valid_tickers = [t for t in tickers if t in price_data]
    if len(valid_tickers) < 5:
        return {"error": "Not enough historical data available."}

    prices_df = pd.DataFrame(price_data).dropna()
    returns_df = prices_df.pct_change().dropna()
    cov_matrix = returns_df.cov().values * 252  # annualize

    # Re-align expected returns with valid tickers
    ticker_to_stock = {s["ticker"]: s for s in stocks}
    valid_stocks = [ticker_to_stock[t] for t in valid_tickers]
    valid_returns = np.array([s["expected_return"] for s in valid_stocks])

    # Stage 3: Markowitz Optimization
    opt_result = optimize_portfolio(
        tickers=valid_tickers,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        risk_level=risk_level,
        target_return=target_return,
    )

    # Stage 4: Monte Carlo Simulation
    horizon_years = HORIZON_YEARS.get(investment_horizon, 3.0)
    weights_array = np.array([opt_result["weights"].get(t, 0) for t in valid_tickers])

    sim_result = run_monte_carlo(
        weights=weights_array,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        initial_value=available_amount,
        horizon_years=horizon_years,
    )

    # Build response
    holdings = []
    for ticker in valid_tickers:
        w = opt_result["weights"].get(ticker, 0)
        if w < 0.01:
            continue
        stock = ticker_to_stock[ticker]
        holdings.append({
            "ticker": ticker,
            "company_name": stock["company_name"],
            "sector": stock["sector"],
            "allocation_pct": round(w * 100, 2),
            "expected_return": round(stock["expected_return"] * 100, 2),
        })

    return {
        "holdings": holdings,
        "risk_score": round(opt_result["portfolio_volatility"] * 100, 2),
        "expected_return_low": round(sim_result["return_low"] * 100, 2),
        "expected_return_high": round(sim_result["return_high"] * 100, 2),
        "portfolio_return": round(opt_result["portfolio_return"] * 100, 2),
        "simulation": sim_result,
        "status": opt_result["status"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_engine/test_pipeline.py -v`
Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: portfolio engine pipeline orchestrating all 4 stages"
```

---

## Task 11: Portfolio API Endpoints

**Files:**
- Create: `backend/app/schemas/portfolio.py`
- Create: `backend/app/api/portfolios.py`
- Create: `backend/tests/test_portfolios.py`
- Modify: `backend/app/main.py` (add portfolios router)

- [ ] **Step 1: Write portfolio API tests**

Create `backend/tests/test_portfolios.py`:
```python
from unittest.mock import patch

PROFILE_PAYLOAD = {
    "risk_level": 3,
    "investment_horizon": "3-5y",
    "available_amount": 50000.00,
    "target_return": 10.0,
    "preferred_sectors": ["Technology"],
    "include_tickers": [],
    "exclude_tickers": [],
}

MOCK_ENGINE_RESULT = {
    "holdings": [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "allocation_pct": 30.0, "expected_return": 12.0},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "allocation_pct": 25.0, "expected_return": 10.5},
        {"ticker": "GOOGL", "company_name": "Alphabet", "sector": "Technology", "allocation_pct": 20.0, "expected_return": 11.0},
        {"ticker": "NVDA", "company_name": "NVIDIA", "sector": "Technology", "allocation_pct": 15.0, "expected_return": 15.0},
        {"ticker": "AMZN", "company_name": "Amazon", "sector": "Technology", "allocation_pct": 10.0, "expected_return": 9.5},
    ],
    "risk_score": 18.5,
    "expected_return_low": 5.2,
    "expected_return_high": 16.8,
    "portfolio_return": 11.5,
    "simulation": {"percentile_10": 42000, "percentile_50": 58000, "percentile_90": 78000, "return_low": 0.052, "return_high": 0.168, "initial_value": 50000, "horizon_years": 4.0, "n_simulations": 10000},
    "status": "optimal",
}


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_generate_portfolio(mock_engine, client, auth_headers):
    # Create profile first
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]

    resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["holdings"]) == 5
    assert data["risk_score"] == 18.5


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_list_portfolios(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)

    resp = client.get("/portfolios", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_archive_portfolio(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    gen_resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    portfolio_id = gen_resp.json()["id"]

    resp = client.patch(f"/portfolios/{portfolio_id}/archive", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_portfolios.py -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Create backend/app/schemas/portfolio.py**

```python
from pydantic import BaseModel


class HoldingResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str
    allocation_pct: float
    expected_return: float


class SimulationResponse(BaseModel):
    percentile_10: float
    percentile_50: float
    percentile_90: float
    return_low: float
    return_high: float
    initial_value: float
    horizon_years: float
    n_simulations: int


class PortfolioResponse(BaseModel):
    id: str
    status: str
    risk_score: float
    expected_return_low: float
    expected_return_high: float
    portfolio_return: float
    total_value: float
    holdings: list[HoldingResponse]
    simulation: SimulationResponse

    model_config = {"from_attributes": True}


class PortfolioListItem(BaseModel):
    id: str
    status: str
    risk_score: float
    expected_return_low: float
    expected_return_high: float
    total_value: float
    created_at: str
```

- [ ] **Step 4: Create backend/app/api/portfolios.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.engine.pipeline import generate_portfolio
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.profile import InvestmentProfile
from app.models.user import User
from app.schemas.portfolio import PortfolioResponse, PortfolioListItem, HoldingResponse, SimulationResponse

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.post("/generate/{profile_id}", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def generate(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(InvestmentProfile).filter(
        InvestmentProfile.id == profile_id,
        InvestmentProfile.user_id == user.id,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    result = generate_portfolio(
        country=user.country,
        risk_level=profile.risk_level,
        investment_horizon=profile.investment_horizon,
        available_amount=float(profile.available_amount),
        target_return=float(profile.target_return) / 100,
        preferred_sectors=profile.preferred_sectors,
        include_tickers=profile.include_tickers,
        exclude_tickers=profile.exclude_tickers,
        db=db,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    portfolio = Portfolio(
        user_id=user.id,
        profile_id=profile.id,
        status="active",
        risk_score=result["risk_score"],
        expected_return_low=result["expected_return_low"],
        expected_return_high=result["expected_return_high"],
        total_value=float(profile.available_amount),
    )
    db.add(portfolio)
    db.flush()

    for h in result["holdings"]:
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            ticker=h["ticker"],
            company_name=h["company_name"],
            sector=h["sector"],
            allocation_pct=h["allocation_pct"],
            expected_return=h["expected_return"],
        )
        db.add(holding)

    db.commit()
    db.refresh(portfolio)

    return PortfolioResponse(
        id=str(portfolio.id),
        status=portfolio.status,
        risk_score=float(portfolio.risk_score),
        expected_return_low=float(portfolio.expected_return_low),
        expected_return_high=float(portfolio.expected_return_high),
        portfolio_return=result["portfolio_return"],
        total_value=float(portfolio.total_value),
        holdings=[HoldingResponse(**h) for h in result["holdings"]],
        simulation=SimulationResponse(**result["simulation"]),
    )


@router.get("", response_model=list[PortfolioListItem])
def list_portfolios(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolios = db.query(Portfolio).filter(Portfolio.user_id == user.id).all()
    return [
        PortfolioListItem(
            id=str(p.id),
            status=p.status,
            risk_score=float(p.risk_score),
            expected_return_low=float(p.expected_return_low),
            expected_return_high=float(p.expected_return_high),
            total_value=float(p.total_value),
            created_at=p.created_at.isoformat(),
        )
        for p in portfolios
    ]


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user.id,
    ).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = db.query(PortfolioHolding).filter(PortfolioHolding.portfolio_id == portfolio.id).all()

    return PortfolioResponse(
        id=str(portfolio.id),
        status=portfolio.status,
        risk_score=float(portfolio.risk_score),
        expected_return_low=float(portfolio.expected_return_low),
        expected_return_high=float(portfolio.expected_return_high),
        portfolio_return=0.0,  # stored in generation, not persisted separately
        total_value=float(portfolio.total_value),
        holdings=[
            HoldingResponse(
                ticker=h.ticker, company_name=h.company_name, sector=h.sector,
                allocation_pct=float(h.allocation_pct), expected_return=float(h.expected_return),
            ) for h in holdings
        ],
        simulation=SimulationResponse(
            percentile_10=0, percentile_50=0, percentile_90=0,
            return_low=float(portfolio.expected_return_low) / 100,
            return_high=float(portfolio.expected_return_high) / 100,
            initial_value=float(portfolio.total_value),
            horizon_years=0, n_simulations=0,
        ),
    )


@router.patch("/{portfolio_id}/archive")
def archive_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user.id,
    ).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    portfolio.status = "archived"
    db.commit()
    return {"id": str(portfolio.id), "status": "archived"}
```

- [ ] **Step 5: Add portfolios router to main.py**

Add to `backend/app/main.py`:
```python
from app.api.portfolios import router as portfolios_router
app.include_router(portfolios_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/test_portfolios.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: portfolio generation, listing, and archiving API endpoints"
```

---

## Task 12: Celery Background Tasks

**Files:**
- Create: `backend/app/tasks/celery_app.py`
- Create: `backend/app/tasks/market_update.py`
- Create: `backend/app/tasks/snapshot_update.py`

- [ ] **Step 1: Create backend/app/tasks/celery_app.py**

```python
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("portfolio_builder", broker=settings.redis_url)

celery_app.conf.beat_schedule = {
    "update-market-data-daily": {
        "task": "app.tasks.market_update.update_all_market_data",
        "schedule": crontab(hour=1, minute=0),  # 1:00 AM daily
    },
    "update-portfolio-snapshots-daily": {
        "task": "app.tasks.snapshot_update.update_all_snapshots",
        "schedule": crontab(hour=2, minute=0),  # 2:00 AM daily
    },
}

celery_app.conf.timezone = "UTC"
celery_app.autodiscover_tasks(["app.tasks"])
```

- [ ] **Step 2: Create backend/app/tasks/market_update.py**

```python
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.data.market import fetch_stock_data, _save_to_cache
from app.models.portfolio import Portfolio, PortfolioHolding
from app.tasks.celery_app import celery_app


@celery_app.task
def update_all_market_data():
    """Fetch latest market data for all tickers in active portfolios."""
    db = SessionLocal()
    try:
        active_portfolios = db.query(Portfolio).filter(Portfolio.status == "active").all()
        ticker_set = set()
        for portfolio in active_portfolios:
            holdings = db.query(PortfolioHolding).filter(
                PortfolioHolding.portfolio_id == portfolio.id
            ).all()
            for h in holdings:
                ticker_set.add(h.ticker)

        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        for ticker in ticker_set:
            try:
                df = fetch_stock_data(ticker, start=start_date, end=end_date)
                _save_to_cache(db, ticker, df)
            except Exception:
                continue
    finally:
        db.close()
```

- [ ] **Step 3: Create backend/app/tasks/snapshot_update.py**

```python
from datetime import date, datetime, timedelta

import yfinance as yf

from app.database import SessionLocal
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.snapshot import PortfolioSnapshot
from app.tasks.celery_app import celery_app


@celery_app.task
def update_all_snapshots():
    """Calculate and save daily portfolio snapshots for active portfolios."""
    db = SessionLocal()
    try:
        today = date.today()
        active_portfolios = db.query(Portfolio).filter(Portfolio.status == "active").all()

        for portfolio in active_portfolios:
            # Check if snapshot already exists for today
            existing = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == portfolio.id,
                PortfolioSnapshot.date == today,
            ).first()
            if existing:
                continue

            holdings = db.query(PortfolioHolding).filter(
                PortfolioHolding.portfolio_id == portfolio.id
            ).all()

            total_value = 0.0
            for h in holdings:
                try:
                    ticker = yf.Ticker(h.ticker)
                    price = ticker.info.get("regularMarketPrice", 0)
                    allocated_amount = float(portfolio.total_value) * float(h.allocation_pct) / 100
                    total_value += allocated_amount * (1 + (price / 100 - 1) * 0.01)  # simplified
                except Exception:
                    total_value += float(portfolio.total_value) * float(h.allocation_pct) / 100

            # Calculate daily return vs previous snapshot
            prev_snapshot = (
                db.query(PortfolioSnapshot)
                .filter(PortfolioSnapshot.portfolio_id == portfolio.id)
                .order_by(PortfolioSnapshot.date.desc())
                .first()
            )
            prev_value = float(prev_snapshot.total_value) if prev_snapshot else float(portfolio.total_value)
            daily_return = (total_value - prev_value) / prev_value if prev_value > 0 else 0

            snapshot = PortfolioSnapshot(
                portfolio_id=portfolio.id,
                date=today,
                total_value=total_value,
                daily_return=daily_return,
            )
            db.add(snapshot)

        db.commit()
    finally:
        db.close()
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: Celery tasks for daily market data and snapshot updates"
```

---

## Task 13: Frontend — Project Setup & Auth

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/tailwind.config.js`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/auth/LoginPage.tsx`
- Create: `frontend/src/auth/RegisterPage.tsx`
- Create: `frontend/src/auth/ProtectedRoute.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/Spinner.tsx`

- [ ] **Step 1: Initialize frontend project**

```bash
cd /Users/roeykarif/Portfolio-Builder
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-router-dom axios recharts tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Configure Tailwind**

Update `frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

Replace `frontend/src/index.css`:
```css
@import "tailwindcss";
```

- [ ] **Step 3: Create frontend/src/api/client.ts**

```ts
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          const resp = await axios.post("/api/auth/refresh", {
            refresh_token: refreshToken,
          });
          localStorage.setItem("access_token", resp.data.access_token);
          localStorage.setItem("refresh_token", resp.data.refresh_token);
          error.config.headers.Authorization = `Bearer ${resp.data.access_token}`;
          return axios(error.config);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
```

- [ ] **Step 4: Create frontend/src/auth/AuthContext.tsx**

```tsx
import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import api from "../api/client";

interface AuthState {
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, country: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    setIsAuthenticated(!!token);
    setLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    const resp = await api.post("/auth/login", { email, password });
    localStorage.setItem("access_token", resp.data.access_token);
    localStorage.setItem("refresh_token", resp.data.refresh_token);
    setIsAuthenticated(true);
  };

  const register = async (email: string, password: string, country: string) => {
    await api.post("/auth/register", { email, password, country });
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 5: Create frontend/src/auth/LoginPage.tsx**

```tsx
import { useState, FormEvent } from "react";
import { useAuth } from "./AuthContext";
import { useNavigate, Link } from "react-router-dom";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch {
      setError("Invalid email or password");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Login</h1>
        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
        <input
          type="email" placeholder="Email" value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full p-3 border rounded mb-4" required
        />
        <input
          type="password" placeholder="Password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full p-3 border rounded mb-6" required
        />
        <button type="submit" className="w-full bg-blue-600 text-white p-3 rounded hover:bg-blue-700">
          Login
        </button>
        <p className="text-center mt-4 text-sm text-gray-600">
          Don't have an account? <Link to="/register" className="text-blue-600">Register</Link>
        </p>
      </form>
    </div>
  );
}
```

- [ ] **Step 6: Create frontend/src/auth/RegisterPage.tsx**

```tsx
import { useState, FormEvent } from "react";
import { useAuth } from "./AuthContext";
import { useNavigate, Link } from "react-router-dom";

const COUNTRIES = [
  { code: "US", name: "United States" },
  { code: "IL", name: "Israel" },
  { code: "GB", name: "United Kingdom" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
  { code: "JP", name: "Japan" },
  { code: "CA", name: "Canada" },
  { code: "AU", name: "Australia" },
];

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [country, setCountry] = useState("US");
  const [error, setError] = useState("");
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await register(email, password, country);
      navigate("/dashboard");
    } catch {
      setError("Registration failed. Email may already be in use.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Create Account</h1>
        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
        <input
          type="email" placeholder="Email" value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full p-3 border rounded mb-4" required
        />
        <input
          type="password" placeholder="Password (min 8 characters)" value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full p-3 border rounded mb-4" required minLength={8}
        />
        <select
          value={country} onChange={(e) => setCountry(e.target.value)}
          className="w-full p-3 border rounded mb-6"
        >
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>{c.name}</option>
          ))}
        </select>
        <button type="submit" className="w-full bg-blue-600 text-white p-3 rounded hover:bg-blue-700">
          Register
        </button>
        <p className="text-center mt-4 text-sm text-gray-600">
          Already have an account? <Link to="/login" className="text-blue-600">Login</Link>
        </p>
      </form>
    </div>
  );
}
```

- [ ] **Step 7: Create frontend/src/auth/ProtectedRoute.tsx**

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import Spinner from "../components/Spinner";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!isAuthenticated) return <Navigate to="/login" />;
  return <>{children}</>;
}
```

- [ ] **Step 8: Create Layout and Spinner components**

Create `frontend/src/components/Spinner.tsx`:
```tsx
export default function Spinner() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
    </div>
  );
}
```

Create `frontend/src/components/Layout.tsx`:
```tsx
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
          <Link to="/dashboard" className="text-xl font-bold text-blue-600">
            Portfolio Builder
          </Link>
          <div className="flex gap-4 items-center">
            <Link to="/dashboard" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link to="/profile/new" className="text-gray-600 hover:text-gray-900">New Portfolio</Link>
            <button onClick={handleLogout} className="text-gray-600 hover:text-gray-900">Logout</button>
          </div>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-4 py-8">
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 9: Create App.tsx with routing**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import LoginPage from "./auth/LoginPage";
import RegisterPage from "./auth/RegisterPage";
import Layout from "./components/Layout";
import DashboardPage from "./dashboard/DashboardPage";
import ProfileForm from "./profile/ProfileForm";
import PortfolioPage from "./portfolio/PortfolioPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/dashboard" element={
            <ProtectedRoute><Layout><DashboardPage /></Layout></ProtectedRoute>
          } />
          <Route path="/profile/new" element={
            <ProtectedRoute><Layout><ProfileForm /></Layout></ProtectedRoute>
          } />
          <Route path="/portfolio/:id" element={
            <ProtectedRoute><Layout><PortfolioPage /></Layout></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

Update `frontend/src/main.tsx`:
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 10: Create placeholder pages** (DashboardPage and ProfileForm — implemented in next tasks)

Create `frontend/src/dashboard/DashboardPage.tsx`:
```tsx
export default function DashboardPage() {
  return <div>Dashboard — coming soon</div>;
}
```

Create `frontend/src/profile/ProfileForm.tsx`:
```tsx
export default function ProfileForm() {
  return <div>Profile Form — coming soon</div>;
}
```

Create `frontend/src/portfolio/PortfolioPage.tsx`:
```tsx
export default function PortfolioPage() {
  return <div>Portfolio — coming soon</div>;
}
```

- [ ] **Step 11: Verify frontend starts**

Run: `cd /Users/roeykarif/Portfolio-Builder/frontend && npm run dev`
Expected: Vite dev server starts at `http://localhost:5173`, login page renders.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "feat: frontend setup with auth, routing, and layout"
```

---

## Task 14: Frontend — Investment Profile Form

**Files:**
- Modify: `frontend/src/profile/ProfileForm.tsx`

- [ ] **Step 1: Implement ProfileForm**

Replace `frontend/src/profile/ProfileForm.tsx`:
```tsx
import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";

const SECTORS = [
  "Technology", "Healthcare", "Energy", "Finance",
  "Consumer", "Real Estate", "Industrial",
];

const HORIZONS = [
  { value: "6m", label: "6 months" },
  { value: "1-3y", label: "1-3 years" },
  { value: "3-5y", label: "3-5 years" },
  { value: "5y+", label: "5+ years" },
];

export default function ProfileForm() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [riskLevel, setRiskLevel] = useState(3);
  const [horizon, setHorizon] = useState("3-5y");
  const [amount, setAmount] = useState("");
  const [targetReturn, setTargetReturn] = useState("");
  const [sectors, setSectors] = useState<string[]>([]);
  const [includeTickers, setIncludeTickers] = useState("");
  const [excludeTickers, setExcludeTickers] = useState("");

  const riskLabels = ["", "Very Conservative", "Conservative", "Balanced", "Aggressive", "Very Aggressive"];

  const toggleSector = (sector: string) => {
    setSectors((prev) =>
      prev.includes(sector) ? prev.filter((s) => s !== sector) : [...prev, sector]
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // Create profile
      const profileResp = await api.post("/profiles", {
        risk_level: riskLevel,
        investment_horizon: horizon,
        available_amount: parseFloat(amount),
        target_return: parseFloat(targetReturn),
        preferred_sectors: sectors,
        include_tickers: includeTickers ? includeTickers.split(",").map((t) => t.trim().toUpperCase()) : [],
        exclude_tickers: excludeTickers ? excludeTickers.split(",").map((t) => t.trim().toUpperCase()) : [],
      });

      // Generate portfolio
      const portfolioResp = await api.post(`/portfolios/generate/${profileResp.data.id}`);
      navigate(`/portfolio/${portfolioResp.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to generate portfolio");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Build Your Portfolio</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {error && <p className="text-red-500 bg-red-50 p-3 rounded">{error}</p>}

        {/* Amount */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Investment Amount ($)
          </label>
          <input
            type="number" min="1000" step="100" value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full p-3 border rounded" required
            placeholder="e.g. 50000"
          />
        </div>

        {/* Risk Level */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Risk Level: <span className="font-bold text-blue-600">{riskLabels[riskLevel]}</span>
          </label>
          <input
            type="range" min="1" max="5" value={riskLevel}
            onChange={(e) => setRiskLevel(parseInt(e.target.value))}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span>Conservative</span><span>Aggressive</span>
          </div>
        </div>

        {/* Horizon */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Investment Horizon</label>
          <div className="grid grid-cols-4 gap-2">
            {HORIZONS.map((h) => (
              <button
                key={h.value} type="button"
                onClick={() => setHorizon(h.value)}
                className={`p-2 rounded border text-sm ${
                  horizon === h.value ? "bg-blue-600 text-white border-blue-600" : "bg-white hover:bg-gray-50"
                }`}
              >
                {h.label}
              </button>
            ))}
          </div>
        </div>

        {/* Target Return */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Target Annual Return (%)
          </label>
          <input
            type="number" min="1" max="50" step="0.5" value={targetReturn}
            onChange={(e) => setTargetReturn(e.target.value)}
            className="w-full p-3 border rounded" required
            placeholder="e.g. 10"
          />
        </div>

        {/* Sectors */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Sectors</label>
          <div className="flex flex-wrap gap-2">
            {SECTORS.map((sector) => (
              <button
                key={sector} type="button"
                onClick={() => toggleSector(sector)}
                className={`px-3 py-1.5 rounded-full text-sm border ${
                  sectors.includes(sector)
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white hover:bg-gray-50"
                }`}
              >
                {sector}
              </button>
            ))}
          </div>
        </div>

        {/* Include/Exclude Tickers */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Include Tickers</label>
            <input
              type="text" value={includeTickers}
              onChange={(e) => setIncludeTickers(e.target.value)}
              className="w-full p-3 border rounded" placeholder="AAPL, MSFT"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Exclude Tickers</label>
            <input
              type="text" value={excludeTickers}
              onChange={(e) => setExcludeTickers(e.target.value)}
              className="w-full p-3 border rounded" placeholder="META, TSLA"
            />
          </div>
        </div>

        <button
          type="submit" disabled={loading || sectors.length === 0}
          className="w-full bg-blue-600 text-white p-3 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Generating Portfolio..." : "Generate Portfolio"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Run: `cd /Users/roeykarif/Portfolio-Builder/frontend && npm run dev`
Navigate to `http://localhost:5173/profile/new` (after logging in).
Expected: Form renders with all fields — slider, sector buttons, ticker inputs.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: investment profile questionnaire form"
```

---

## Task 15: Frontend — Portfolio Results Page

**Files:**
- Modify: `frontend/src/portfolio/PortfolioPage.tsx`
- Create: `frontend/src/portfolio/AllocationChart.tsx`
- Create: `frontend/src/portfolio/HoldingsTable.tsx`
- Create: `frontend/src/portfolio/MonteCarloChart.tsx`
- Create: `frontend/src/portfolio/RiskComparison.tsx`
- Create: `frontend/src/portfolio/DisclaimerBanner.tsx`

- [ ] **Step 1: Create DisclaimerBanner**

Create `frontend/src/portfolio/DisclaimerBanner.tsx`:
```tsx
export default function DisclaimerBanner() {
  return (
    <div className="bg-red-600 text-white p-6 rounded-lg text-center mb-8">
      <p className="text-xl font-bold mb-2">IMPORTANT NOTICE</p>
      <p className="text-lg">
        This is a recommendation only, not certified investment advice.
        We do not guarantee any results. Past performance does not guarantee future returns.
        Always consult a licensed financial advisor before making investment decisions.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Create AllocationChart**

Create `frontend/src/portfolio/AllocationChart.tsx`:
```tsx
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface Holding {
  ticker: string;
  company_name: string;
  allocation_pct: number;
}

const COLORS = ["#2563eb", "#7c3aed", "#059669", "#d97706", "#dc2626", "#0891b2", "#4f46e5", "#be123c"];

export default function AllocationChart({ holdings }: { holdings: Holding[] }) {
  const data = holdings.map((h) => ({
    name: `${h.ticker} (${h.allocation_pct}%)`,
    value: h.allocation_pct,
  }));

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-4">Portfolio Allocation</h2>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 3: Create HoldingsTable**

Create `frontend/src/portfolio/HoldingsTable.tsx`:
```tsx
interface Holding {
  ticker: string;
  company_name: string;
  sector: string;
  allocation_pct: number;
  expected_return: number;
}

export default function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-4">Holdings</h2>
      <table className="w-full text-left">
        <thead>
          <tr className="border-b text-sm text-gray-500">
            <th className="py-2">Ticker</th>
            <th>Company</th>
            <th>Sector</th>
            <th className="text-right">Allocation</th>
            <th className="text-right">Expected Return</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.ticker} className="border-b hover:bg-gray-50">
              <td className="py-3 font-mono font-bold">{h.ticker}</td>
              <td>{h.company_name}</td>
              <td className="text-sm text-gray-600">{h.sector}</td>
              <td className="text-right">{h.allocation_pct}%</td>
              <td className="text-right text-green-600">{h.expected_return}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Create MonteCarloChart**

Create `frontend/src/portfolio/MonteCarloChart.tsx`:
```tsx
interface SimulationData {
  percentile_10: number;
  percentile_50: number;
  percentile_90: number;
  return_low: number;
  return_high: number;
  initial_value: number;
  horizon_years: number;
}

export default function MonteCarloChart({ simulation }: { simulation: SimulationData }) {
  const formatCurrency = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

  const formatPct = (n: number) => `${(n * 100).toFixed(1)}%`;

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-4">Monte Carlo Simulation</h2>
      <p className="text-sm text-gray-500 mb-4">
        Based on {simulation.horizon_years} year horizon, 10,000 simulated scenarios
      </p>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-4 bg-red-50 rounded">
          <p className="text-sm text-gray-500">Worst Case (10th %ile)</p>
          <p className="text-xl font-bold text-red-600">{formatCurrency(simulation.percentile_10)}</p>
          <p className="text-sm text-red-500">{formatPct(simulation.return_low)} / year</p>
        </div>
        <div className="text-center p-4 bg-blue-50 rounded">
          <p className="text-sm text-gray-500">Median (50th %ile)</p>
          <p className="text-xl font-bold text-blue-600">{formatCurrency(simulation.percentile_50)}</p>
        </div>
        <div className="text-center p-4 bg-green-50 rounded">
          <p className="text-sm text-gray-500">Best Case (90th %ile)</p>
          <p className="text-xl font-bold text-green-600">{formatCurrency(simulation.percentile_90)}</p>
          <p className="text-sm text-green-500">{formatPct(simulation.return_high)} / year</p>
        </div>
      </div>

      <p className="text-sm text-gray-500 text-center">
        With 80% probability, your portfolio value after {simulation.horizon_years} years
        will be between {formatCurrency(simulation.percentile_10)} and {formatCurrency(simulation.percentile_90)}
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Create RiskComparison**

Create `frontend/src/portfolio/RiskComparison.tsx`:
```tsx
interface Props {
  riskScore: number;
  expectedReturnLow: number;
  expectedReturnHigh: number;
}

export default function RiskComparison({ riskScore, expectedReturnLow, expectedReturnHigh }: Props) {
  const riskLabel = riskScore < 10 ? "Low" : riskScore < 20 ? "Moderate" : riskScore < 30 ? "High" : "Very High";
  const riskColor = riskScore < 10 ? "text-green-600" : riskScore < 20 ? "text-yellow-600" : riskScore < 30 ? "text-orange-600" : "text-red-600";

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-4">Risk Assessment</h2>
      <div className="flex items-center gap-6">
        <div className="text-center">
          <p className="text-sm text-gray-500">Risk Score</p>
          <p className={`text-3xl font-bold ${riskColor}`}>{riskScore}%</p>
          <p className={`text-sm font-medium ${riskColor}`}>{riskLabel} Volatility</p>
        </div>
        <div className="flex-1">
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className="bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 h-4 rounded-full"
              style={{ width: `${Math.min(riskScore * 2.5, 100)}%` }}
            />
          </div>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-500">Expected Return</p>
          <p className="text-xl font-bold text-blue-600">
            {expectedReturnLow}% — {expectedReturnHigh}%
          </p>
          <p className="text-sm text-gray-400">annual</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create BacktestChart**

Create `frontend/src/portfolio/BacktestChart.tsx`:
```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface BacktestPoint {
  date: string;
  value: number;
}

export default function BacktestChart({ data, initialValue }: { data: BacktestPoint[]; initialValue: number }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-semibold mb-4">Historical Backtest</h2>
        <p className="text-gray-500 text-sm">Backtest data not available</p>
      </div>
    );
  }

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-2">Historical Backtest</h2>
      <p className="text-sm text-gray-500 mb-4">
        If you had invested {formatCurrency(initialValue)} with this allocation
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
          <Tooltip formatter={(v: number) => formatCurrency(v)} />
          <Line type="monotone" dataKey="value" stroke="#2563eb" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 7: Implement PortfolioPage**

Replace `frontend/src/portfolio/PortfolioPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api/client";
import Spinner from "../components/Spinner";
import DisclaimerBanner from "./DisclaimerBanner";
import AllocationChart from "./AllocationChart";
import BacktestChart from "./BacktestChart";
import HoldingsTable from "./HoldingsTable";
import MonteCarloChart from "./MonteCarloChart";
import RiskComparison from "./RiskComparison";

interface PortfolioData {
  id: string;
  status: string;
  risk_score: number;
  expected_return_low: number;
  expected_return_high: number;
  portfolio_return: number;
  total_value: number;
  holdings: Array<{
    ticker: string;
    company_name: string;
    sector: string;
    allocation_pct: number;
    expected_return: number;
  }>;
  simulation: {
    percentile_10: number;
    percentile_50: number;
    percentile_90: number;
    return_low: number;
    return_high: number;
    initial_value: number;
    horizon_years: number;
    n_simulations: number;
  };
}

export default function PortfolioPage() {
  const { id } = useParams<{ id: string }>();
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/portfolios/${id}`).then((resp) => {
      setPortfolio(resp.data);
      setLoading(false);
    });
  }, [id]);

  if (loading || !portfolio) return <Spinner />;

  return (
    <div className="space-y-6">
      <DisclaimerBanner />

      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Your Portfolio</h1>
        <span className="text-sm text-gray-500">
          Total Investment: ${portfolio.total_value.toLocaleString()}
        </span>
      </div>

      <RiskComparison
        riskScore={portfolio.risk_score}
        expectedReturnLow={portfolio.expected_return_low}
        expectedReturnHigh={portfolio.expected_return_high}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AllocationChart holdings={portfolio.holdings} />
        <MonteCarloChart simulation={portfolio.simulation} />
      </div>

      <BacktestChart data={portfolio.backtest || []} initialValue={portfolio.total_value} />

      <HoldingsTable holdings={portfolio.holdings} />
    </div>
  );
}
```

- [ ] **Step 7: Verify in browser**

Navigate to a portfolio page (after generating one).
Expected: Disclaimer banner, risk assessment, pie chart, Monte Carlo results, holdings table all render.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: portfolio results page with charts, risk, and disclaimer"
```

---

## Task 16: Frontend — Dashboard

**Files:**
- Modify: `frontend/src/dashboard/DashboardPage.tsx`
- Create: `frontend/src/dashboard/PortfolioCard.tsx`

- [ ] **Step 1: Create PortfolioCard**

Create `frontend/src/dashboard/PortfolioCard.tsx`:
```tsx
import { Link } from "react-router-dom";

interface Props {
  id: string;
  status: string;
  riskScore: number;
  expectedReturnLow: number;
  expectedReturnHigh: number;
  totalValue: number;
  createdAt: string;
}

export default function PortfolioCard({ id, status, riskScore, expectedReturnLow, expectedReturnHigh, totalValue, createdAt }: Props) {
  return (
    <Link to={`/portfolio/${id}`} className="block bg-white p-6 rounded-lg shadow hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <span className="text-sm text-gray-400">{new Date(createdAt).toLocaleDateString()}</span>
        <span className={`text-xs px-2 py-1 rounded-full ${
          status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
        }`}>
          {status}
        </span>
      </div>
      <p className="text-2xl font-bold mb-1">${totalValue.toLocaleString()}</p>
      <p className="text-sm text-gray-600 mb-2">
        Expected: {expectedReturnLow}% — {expectedReturnHigh}% annual
      </p>
      <p className="text-sm text-gray-500">Risk score: {riskScore}%</p>
    </Link>
  );
}
```

- [ ] **Step 2: Implement DashboardPage**

Replace `frontend/src/dashboard/DashboardPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";
import PortfolioCard from "./PortfolioCard";
import Spinner from "../components/Spinner";

interface PortfolioItem {
  id: string;
  status: string;
  risk_score: number;
  expected_return_low: number;
  expected_return_high: number;
  total_value: number;
  created_at: string;
}

export default function DashboardPage() {
  const [portfolios, setPortfolios] = useState<PortfolioItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/portfolios").then((resp) => {
      setPortfolios(resp.data);
      setLoading(false);
    });
  }, []);

  if (loading) return <Spinner />;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">My Portfolios</h1>
        <Link to="/profile/new" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          + New Portfolio
        </Link>
      </div>

      {portfolios.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg mb-4">No portfolios yet</p>
          <Link to="/profile/new" className="text-blue-600 hover:underline">
            Create your first portfolio
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {portfolios.map((p) => (
            <PortfolioCard
              key={p.id}
              id={p.id}
              status={p.status}
              riskScore={p.risk_score}
              expectedReturnLow={p.expected_return_low}
              expectedReturnHigh={p.expected_return_high}
              totalValue={p.total_value}
              createdAt={p.created_at}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify in browser**

Navigate to `http://localhost:5173/dashboard`.
Expected: Empty state with "Create your first portfolio" link, or portfolio cards if any exist.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: dashboard page with portfolio cards"
```

---

## Task 17: Country Restrictions Seed Data

**Files:**
- Create: `backend/app/data/seed.py`
- Add management command to seed DB

- [ ] **Step 1: Create backend/app/data/seed.py**

```python
from sqlalchemy.orm import Session

from app.data.country_data import COUNTRY_EXCHANGES
from app.models.country import CountryRestriction


def seed_country_restrictions(db: Session) -> None:
    """Seed country restriction data into the database."""
    for code, exchanges in COUNTRY_EXCHANGES.items():
        existing = db.query(CountryRestriction).filter(CountryRestriction.country_code == code).first()
        if not existing:
            db.add(CountryRestriction(country_code=code, allowed_exchanges=exchanges))
    db.commit()
```

- [ ] **Step 2: Add startup event to main.py**

Add to `backend/app/main.py`:
```python
from app.database import SessionLocal
from app.data.seed import seed_country_restrictions

@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        seed_country_restrictions(db)
    finally:
        db.close()
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: seed country restriction data on startup"
```

---

## Task 18: End-to-End Smoke Test

- [ ] **Step 1: Start all services**

```bash
cd /Users/roeykarif/Portfolio-Builder
docker compose up --build -d
cd frontend && npm run dev &
```

- [ ] **Step 2: Manual smoke test**

1. Open `http://localhost:5173`
2. Register a new account (US country)
3. Navigate to "New Portfolio"
4. Fill form: $50,000, Balanced risk, 3-5 years, Technology + Healthcare, 10% target
5. Submit → should see portfolio results with pie chart, risk score, Monte Carlo
6. Navigate to Dashboard → should see the portfolio card
7. Click the card → should see full portfolio details
8. Verify disclaimer banner is large and prominent

- [ ] **Step 3: Run all backend tests**

Run: `cd /Users/roeykarif/Portfolio-Builder/backend && python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: end-to-end verification complete"
```
