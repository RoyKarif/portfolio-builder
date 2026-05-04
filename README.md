# Portfolio Builder

> Full-stack web application for personal investment portfolio construction.
> Uses **Markowitz Mean-Variance Optimization** (convex optimization) and
> **Monte Carlo simulation** to project the distribution of future outcomes.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

---

## Overview

A user signs up, fills in a short form (investment amount, time horizon,
risk level, asset preferences, country of residence), and the app returns:

- **Optimal weights** across a curated universe of 32 ETFs
- **Expected return, volatility, and Sharpe ratio**
- **Monte Carlo fan chart** of 10,000 simulated paths
- **Histogram of final values** with Value-at-Risk
- **Saved portfolios** they can revisit (each with reproducible Monte Carlo)

---

## Tech Stack

| Layer | Stack |
|-------|-------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2, cvxpy, NumPy, pandas |
| **Database** | PostgreSQL 16 with JSONB, Alembic migrations |
| **Auth** | JWT (HS256), bcrypt |
| **Frontend** | React 18, TypeScript (strict), Vite, Tailwind CSS, recharts |
| **Infra** | Docker Compose (3 services), GitHub Actions CI |
| **Testing** | pytest (33+ tests across engine, data, and API layers) |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       DOCKER COMPOSE                         │
│                                                              │
│   ┌──────────┐   HTTP    ┌──────────────┐   SQL  ┌────────┐ │
│   │ Frontend │──────────▶│  Backend API │───────▶│   DB   │ │
│   │ React/TS │◀──────────│   FastAPI    │◀───────│ Postgres│ │
│   │  :5173   │           │    :8000     │        │        │ │
│   └──────────┘           └──────┬───────┘        └────────┘ │
│                                 │                            │
│                                 ▼ (lazy, on portfolio build) │
│                          ┌──────────────┐                    │
│                          │   yfinance   │                    │
│                          └──────────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

The codebase is built with **dependency inversion** in three layers:

- **Engine** (`backend/app/engine/`) — pure math. Doesn't know about HTTP
  or the database. Takes NumPy arrays in, returns NumPy arrays out.
- **Data** (`backend/app/data/`) — repository pattern over SQLAlchemy.
  The engine and the API never talk to SQL directly.
- **API** (`backend/app/api/`) — FastAPI route handlers. Pure orchestration:
  parse the request, call data + engine, persist, return JSON.

Each layer is independently testable.

---

## Math Models Used

### 1. Markowitz Mean-Variance Optimization

Solves the constrained quadratic program

```
maximize    μᵀw                          (expected portfolio return)
subject to  wᵀΣw ≤ σ_target²             (volatility budget)
            sum(w) = 1
            0 ≤ w_i ≤ 0.20               (per-asset diversification cap)
            Σ_{i ∈ class} w_i ≤ class_cap  (per-class cap)
```

Implemented with **cvxpy**. Per-class caps are *asymmetric*: equity caps
at 70%, commodities and real estate at 30%, bonds and cash uncapped — so
low-risk portfolios can go heavy on bonds while high-risk portfolios are
forced to diversify across asset classes.

### 2. Monte Carlo Simulation

Generates 10,000 future paths under multivariate-normal returns. Optimized
by sampling directly from the *portfolio's univariate Normal*
`wᵀr ~ N(wᵀμ, wᵀΣw)` instead of from the asset MVN — a 32× speedup
for our universe size, with identical statistical results.

---

## Quick Start

```bash
git clone https://github.com/RoyKarif/portfolio-builder
cd portfolio-builder
cp .env.example .env
# Edit JWT_SECRET (e.g.: openssl rand -hex 32)

./dev.sh
```

This brings up the full stack (Postgres + backend + frontend), applies
migrations, prints the URLs, and tails logs. Open http://localhost:5173.

The first portfolio build lazily fetches 10 years of daily prices from
yfinance (~10 s for the full universe, in parallel). All subsequent
builds reuse the DB cache. If yfinance is unavailable, the system falls
back transparently to a synthetic single-factor model with realistic
cross-asset correlations — the demo always works.

---

## Project Layout

```
backend/
├── app/
│   ├── engine/      # MVO + Monte Carlo (pure math, no I/O)
│   ├── data/        # Repositories + yfinance adapter + price cache
│   ├── auth/        # bcrypt + JWT + FastAPI dependency
│   ├── api/         # 7 routes (auth, universe, portfolios)
│   ├── models/      # 4 SQLAlchemy ORM models
│   ├── schemas/     # Pydantic request/response schemas
│   ├── config.py    # Settings (env vars)
│   ├── db.py        # Session factory + get_db dependency
│   └── main.py      # FastAPI app + lifespan startup
├── alembic/         # Schema migrations
├── scripts/         # Optional manual seed; synthetic price generator
└── tests/           # ~33 pytest tests

frontend/
├── src/
│   ├── api/         # axios client + per-domain wrappers
│   ├── auth/        # AuthContext + Login/Register/Protected route
│   ├── pages/       # 5 pages (Build / List / Detail / Login / Register)
│   ├── components/  # 9 components (RiskSlider, FanChart, …)
│   └── types/       # TypeScript mirrors of Pydantic schemas
└── (Vite + Tailwind config)

docker-compose.yml   # 3 services
.github/workflows/   # CI (pytest + frontend build)
```

Detailed file-by-file documentation is in [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md).

---

## Tests

```bash
make test
```

Pyramid:
- **Engine** (~17 tests): MVO constraints, Monte Carlo reproducibility,
  return/statistics math.
- **API** (~12 tests): auth flow, full portfolio build, cross-user
  authorization.
- **Data** (~4 tests): repository round-trips.

CI runs the full suite on every push, against a real Postgres service
container.

---

## Notes

This is a personal learning project, not investment advice. It explores
classical portfolio theory with practical software-engineering structure
(layered architecture, full type-checking, CI, Docker). The math models
themselves are textbook — the project's value is in how cleanly they
plug into a real web app.
