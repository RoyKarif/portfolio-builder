# Portfolio Builder — Design Spec

## Overview

A web application that builds personalized stock portfolios for beginner investors. Users input their financial profile (risk tolerance, budget, preferences) and the system generates an optimized portfolio using mathematical models, with a rough forecast of expected performance.

**Target audience:** Regular people who want to start investing — UI must be simple and accessible.

**This is a new standalone project**, separate from any existing codebase.

---

## Architecture

```
┌─────────────────────┐
│   React Frontend    │
│  (Vite + TypeScript)│
│  Charts, Forms, UI  │
└────────┬────────────┘
         │ REST API
┌────────▼────────────┐
│   FastAPI Backend   │
│  Auth, API Routes   │
├─────────────────────┤
│   Portfolio Engine   │
│  ┌───────────────┐  │
│  │  ML Predictor  │  │
│  │  (XGBoost)     │  │
│  └───────┬───────┘  │
│  ┌───────▼───────┐  │
│  │  Markowitz     │  │
│  │  Optimizer     │  │
│  └───────┬───────┘  │
│  ┌───────▼───────┐  │
│  │  Monte Carlo   │  │
│  │  Simulation    │  │
│  └───────────────┘  │
├─────────────────────┤
│   Market Data       │
│   (yfinance)        │
├─────────────────────┤
│   PostgreSQL DB     │
│   Users, Portfolios │
└─────────────────────┘
```

Three main components:

1. **Frontend (React)** — Input forms, portfolio display, charts, disclaimer
2. **Backend (FastAPI)** — User auth, API, and the Portfolio Engine containing all mathematical logic
3. **Database (PostgreSQL)** — Users, risk profiles, saved portfolios, computation history

Market data is fetched from yfinance and cached in the DB to avoid redundant API calls.

---

## User Flow

### Step 1 — Registration / Login
- Email + password registration
- JWT authentication

### Step 2 — Investment Profile Questionnaire
The user fills out a form with:
- **Country** (determines which exchanges/stocks are available)
- **Available investment amount**
- **Risk level** (slider: Conservative ← Balanced ← Aggressive)
- **Investment horizon** (6 months / 1-3 years / 3-5 years / 5+ years)
- **Preferred sectors** (multi-select: Technology, Healthcare, Energy, Finance, Consumer, Real Estate, Industrial)
- **Specific tickers to include/exclude**
- **Target annual return** (percentage)

### Step 3 — Portfolio Calculation & Display
The system runs the engine and presents:
- **Pie chart** of stock allocation (e.g., AAPL 25%, MSFT 15%...)
- **Overall risk score** with textual explanation
- **Expected return range** (e.g., 8%-14% annual)
- **Backtesting chart** — "if you had invested this way 5 years ago"
- **Risk comparison** — what happens if you increase/decrease risk by one level
- **Large prominent disclaimer banner** — "This is a recommendation only, not certified investment advice. We do not guarantee any results."

### Step 4 — Save & Track
- User saves the portfolio
- Receives periodic updates (daily/weekly) on performance
- Option to build a new portfolio or modify parameters

---

## Portfolio Engine — Mathematical Logic

### Stage 1 — Universe Selection (Stock Filtering)
- Filter by user's country → only available exchanges
- Filter by selected sectors
- Remove excluded tickers, add included tickers
- Filter out stocks with low liquidity (volume threshold)

### Stage 2 — Expected Return Estimation (ML Predictor)
- XGBoost trained on historical data
- Features: historical returns, volatility, financial multiples (P/E, P/B, dividend yield), momentum, moving averages
- Output: expected return per stock
- Model retrained periodically (weekly/monthly)

### Stage 3 — Markowitz Optimization
- Input: expected returns vector (from ML) + covariance matrix (from historical data)
- Constraints:
  - User's risk level → caps maximum volatility
  - Target return goal
  - Single stock cannot exceed 30% of portfolio (diversification)
  - Minimum 5 stocks in portfolio
- Output: optimal allocation percentage per stock
- Libraries: `scipy.optimize` or `cvxpy`

### Stage 4 — Monte Carlo Simulation
- Run 10,000 random scenarios forward (based on selected investment horizon)
- Based on expected returns and covariance matrix
- Calculate: median, 10th percentile (worst case), 90th percentile (best case)
- Display to user as range: "With 80% probability, return will be between X% and Y%"

---

## Data Model

### Users
| Column | Type |
|--------|------|
| id | UUID PK |
| email | string, unique |
| password_hash | string |
| country | string |
| created_at | timestamp |

### InvestmentProfiles
| Column | Type |
|--------|------|
| id | UUID PK |
| user_id | FK → Users |
| risk_level | int (1-5) |
| investment_horizon | string |
| available_amount | decimal |
| target_return | decimal |
| preferred_sectors | JSON |
| include_tickers | JSON |
| exclude_tickers | JSON |

### Portfolios
| Column | Type |
|--------|------|
| id | UUID PK |
| user_id | FK → Users |
| profile_id | FK → InvestmentProfiles |
| created_at | timestamp |
| status | string (active/archived) |
| risk_score | decimal |
| expected_return_low | decimal |
| expected_return_high | decimal |
| total_value | decimal |

### PortfolioHoldings
| Column | Type |
|--------|------|
| id | UUID PK |
| portfolio_id | FK → Portfolios |
| ticker | string |
| company_name | string |
| sector | string |
| allocation_pct | decimal |
| expected_return | decimal |

### MarketDataCache
| Column | Type |
|--------|------|
| ticker | string |
| date | date |
| open | decimal |
| close | decimal |
| high | decimal |
| low | decimal |
| volume | bigint |
| pe_ratio | decimal |
| pb_ratio | decimal |
| dividend_yield | decimal |
| last_updated | timestamp |

### PortfolioSnapshots
| Column | Type |
|--------|------|
| id | UUID PK |
| portfolio_id | FK → Portfolios |
| date | date |
| total_value | decimal |
| daily_return | decimal |

### CountryRestrictions
| Column | Type |
|--------|------|
| country_code | string PK |
| allowed_exchanges | JSON |

---

## Technology Stack

### Backend
- Python 3.12 + FastAPI
- SQLAlchemy + Alembic (ORM + migrations)
- PostgreSQL
- JWT authentication (python-jose + passlib)
- `yfinance` — market data
- `numpy` + `scipy` — mathematical computations
- `cvxpy` — Markowitz optimization
- `scikit-learn` / `xgboost` — ML model
- `celery` + `redis` — background jobs (periodic data updates, model retraining)

### Frontend
- React 18 + TypeScript + Vite
- Tailwind CSS — styling
- Recharts — charts (pie chart, performance graph, Monte Carlo distribution)
- React Router — navigation
- Axios — API calls

### Infrastructure
- Docker Compose (FastAPI + PostgreSQL + Redis)
- Celery Beat — scheduler for periodic updates (market data fetching, snapshot computation)

### Backend Directory Structure
```
backend/
├── app/
│   ├── main.py
│   ├── auth/          # JWT, login, register
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── api/           # route handlers
│   ├── engine/
│   │   ├── universe.py      # stock filtering
│   │   ├── predictor.py     # XGBoost ML model
│   │   ├── optimizer.py     # Markowitz optimization
│   │   ├── simulator.py     # Monte Carlo
│   │   └── pipeline.py      # orchestrates all stages
│   ├── services/      # business logic
│   ├── tasks/         # Celery tasks
│   └── data/          # market data fetching & caching
```

---

## Security, Error Handling & Limitations

### Security
- Passwords hashed with bcrypt
- JWT with limited expiry + refresh tokens
- Rate limiting on API endpoints (prevent abuse)
- Input validation on all user inputs (Pydantic)
- No cross-user data exposure

### Known Limitations (displayed to user)
- Forecast is a rough estimate only — past performance does not guarantee future results
- System does not account for: taxation, broker fees, extreme macro events (wars, crashes)
- Data updates with delay (not tick-by-tick)
- ML model can be wrong — therefore ranges are shown, not exact numbers

### Error Handling
- yfinance unavailable → fallback to cached data + notify user
- Selected stock no longer traded → notification + suggest alternative
- Optimization doesn't converge (conflicting constraints) → message that target return is unrealistic at selected risk level

---

## Update Modes

The system supports two update modes (user selectable):
1. **Periodic** — portfolio data refreshes daily/weekly automatically
2. **Real-time** — live price updates (to be added as a future enhancement, starting with periodic)
