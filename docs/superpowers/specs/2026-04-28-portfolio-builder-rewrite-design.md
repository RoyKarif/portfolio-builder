# Portfolio Builder — Rewrite Design

**תאריך:** 2026-04-28
**סטטוס:** Design — ממתין לאישור משתמש לפני כתיבת תכנית ביצוע
**מחבר:** Roy Karif (עם Claude)

---

## 1. רקע ומטרה

### 1.1 רקע

האיטרציה הקיימת של Portfolio Builder התפתחה לכלי quant מורכב הכולל HRP/MVO routing, defensive universe injection, walk-forward backtesting, ועוד. הבעיה: השכבות התרבו עד כדי שלא ניתן להגן על כל פרט בראיון עבודה. הקוד הוא תקף — אבל הוא **אינו ניתן להגנה מלאה** על ידי המחבר היחיד.

### 1.2 מטרה

שכתוב מלא של הפרויקט במטרה אחת בלבד: **פרויקט שאני יכול להבין ולהגן עליו ב-100%, מה-DB דרך ה-API ועד הקוד הספציפי של כל פונקציה.**

זה לא שכתוב לטובת ביצועים, פיצ'רים, או scale. זה שכתוב לטובת **בעלות מלאה** על כל שורה.

### 1.3 קריטריונים להצלחה

הפרויקט יוגדר כמוצלח אם:

1. ניתן לכתוב על הלוח, מהזיכרון, את הניסוח המתמטי של MVO ושל Monte Carlo.
2. ניתן להסביר כל בחירת ספרייה (FastAPI, cvxpy, recharts וכו') ואת האלטרנטיבות.
3. ניתן להסביר את כל ה-schema של DB וכל אינדקס.
4. ניתן להריץ את הפרויקט מאפס בעזרת README ב-7 פקודות.
5. ניתן לכתוב משפט אחד ב-CV שכל מילה בו אמינה.

---

## 2. החלטות מפתח (אישורים מתועדים)

| החלטה | הבחירה | אישור |
|---|---|---|
| מודלים מתמטיים | MVO + Monte Carlo | ✅ |
| היקף משתמשים | logged-in users + saved portfolios | ✅ |
| יקום נכסים | Hybrid: ~20 ETFs curated + custom tickers via yfinance | ✅ |
| מודל סיכון | Slider 1–5 → target volatility (אילוץ קשיח) | ✅ |
| שדות טופס | סכום, סיכון, בחירת נכסים (include/exclude), אופק | ✅ |
| תוכן עמוד תוצאות | משקלות + סטטיסטיקה + Efficient Frontier + Fan Chart + Histogram + VaR | ✅ |
| Stack | FastAPI + Postgres + React/Vite + Docker (drop Celery/Redis) | ✅ |
| Auth | JWT (HS256), bcrypt | ✅ |

---

## 3. ארכיטקטורה

### 3.1 סקירה ברמת המערכת

```
┌──────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE                              │
│   ┌────────────┐      ┌────────────────┐      ┌──────────────────┐  │
│   │  Frontend  │──→──│   Backend API   │──→──│    PostgreSQL    │  │
│   │  React+Vite│ HTTP │     FastAPI     │ SQL │  (4 tables)      │  │
│   │   :5173    │←──── │      :8000      │ ←── │                  │  │
│   └────────────┘      └────────┬────────┘      └──────────────────┘  │
│                                │                                     │
│                                ▼ (only when adding custom ticker)    │
│                        ┌──────────────┐                              │
│                        │   yfinance   │                              │
│                        └──────────────┘                              │
└──────────────────────────────────────────────────────────────────────┘
```

**שלוש סרוויסים בלבד.** אין Celery, אין Redis, אין worker. כל הבקשות סינכרוניות.

### 3.2 עיקרון ארכיטקטוני: תלויות זורמות פנימה

```
api  ─→  engine + data
            │
            └─→  models / schemas
```

- ה-**API** יודע על HTTP ועל ה-engine ועל ה-data.
- ה-**engine** לא יודע על HTTP או על DB. מקבל `np.ndarray` או `pd.DataFrame`, מחזיר `np.ndarray` או `dict`.
- ה-**data** לא יודע על HTTP. מקבל `Session` ו-args, מחזיר `pd.DataFrame` או entity.

**מה זה נותן:** אפשר לבדוק את ה-engine **בלי DB**, אפשר לבדוק את ה-data **בלי HTTP**. בידוד מלא.

---

## 4. שכבת הנתונים (PostgreSQL)

ארבע טבלאות.

### 4.1 `users`

```sql
CREATE TABLE users (
    id            SERIAL       PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);
```

**הסבר:**
- `id SERIAL PRIMARY KEY` — מזהה אוטומטי. `SERIAL` = `INTEGER` שגדל אוטומטית.
- `email UNIQUE` — אילוץ ברמת DB. שני משתמשים לא יכולים להירשם עם אותו מייל גם אם הקוד באג.
- `password_hash` — תוצאה של `bcrypt(password)`, לא הסיסמה. ב-bcrypt יש salt משובץ → אותה סיסמה אצל שני משתמשים → hash שונה.
- אינדקס על `email` מאיץ lookup בהתחברות.

### 4.2 `assets`

```sql
CREATE TABLE assets (
    ticker      VARCHAR(10)  PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    asset_class VARCHAR(20)  NOT NULL,
    is_curated  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);
```

**הסבר:**
- `ticker` הוא ה-PK עצמו (לא צריך id נפרד) כי הוא מזהה טבעי, יחודי, וקצר.
- `asset_class`: `equity`, `bond`, `commodity`, `real_estate`, `cash`. מחרוזת ולא ENUM כדי לא לחייב migration כשמוסיפים סוג.
- `is_curated` מבדיל בין 20 ה-ETFs הזרועים לבין tickers שהמשתמש הוסיף דרך yfinance.

### 4.3 `prices`

```sql
CREATE TABLE prices (
    ticker VARCHAR(10) NOT NULL REFERENCES assets(ticker) ON DELETE CASCADE,
    date   DATE        NOT NULL,
    close  NUMERIC(12,4) NOT NULL,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX idx_prices_ticker_date ON prices(ticker, date DESC);
```

**הסבר:**
- `REFERENCES assets(ticker)` עם `ON DELETE CASCADE` — אי אפשר להכניס מחיר ל-ticker שלא קיים, ומחיקת נכס מנקה את המחירים שלו.
- `NUMERIC(12,4)` ולא `FLOAT` — בכסף לא רוצים שגיאות עיגול בינאריות.
- PK מורכב `(ticker, date)` — שני הדברים יחד מזהים שורה. אסור שני מחירים לאותו ticker באותו תאריך.
- אינדקס נוסף עם `DESC` לאופטימיזציה של "10 שנים אחרונות של SPY".

**גודל מצופה:** 25 ETFs × 2,500 ימי מסחר = 62,500 שורות. ניהוליות.

### 4.4 `portfolios`

```sql
CREATE TABLE portfolios (
    id                  SERIAL       PRIMARY KEY,
    user_id             INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),

    -- inputs
    amount              NUMERIC(14,2) NOT NULL,
    risk_level          SMALLINT      NOT NULL CHECK (risk_level BETWEEN 1 AND 5),
    horizon_years       SMALLINT      NOT NULL CHECK (horizon_years BETWEEN 1 AND 30),
    target_volatility   NUMERIC(6,4)  NOT NULL,

    -- outputs
    weights             JSONB         NOT NULL,
    expected_return     NUMERIC(6,4)  NOT NULL,
    expected_volatility NUMERIC(6,4)  NOT NULL,
    sharpe_ratio        NUMERIC(6,4)  NOT NULL,
    mc_summary          JSONB         NOT NULL,
    mc_seed             INTEGER       NOT NULL
);
CREATE INDEX idx_portfolios_user_created ON portfolios(user_id, created_at DESC);
```

**הסבר:**
- `CHECK (risk_level BETWEEN 1 AND 5)` — אילוץ ברמת DB. שכבת הגנה כפולה גם אם הקוד באג.
- `target_volatility` נשמר אף שאפשר לחשב מ-`risk_level` — לטובת **reproducibility** אם המיפוי משתנה בעתיד.
- `weights JSONB` — `{ "SPY": 0.45, "AGG": 0.30, ... }`. נבחר על פני טבלה נפרדת כי תמיד קוראים את כל המשקלות יחד.
- `mc_summary JSONB` — `{ "p5", "p25", "p50", "p75", "p95", "var_5", "timeline": [...] }`. **לא** שומרים את כל המסלולים (10,000 × 252 × 10 = 25M).
- `mc_seed` — לשחזור מדויק של ה-fan chart בעת טעינה חוזרת.

### 4.5 קשרים

```
users (1) ──────< portfolios (N)
assets (1) ─────< prices (N)
```

אין קשר ישיר בין `portfolios` ל-`assets` (המשקלות ב-JSONB) — מודע לזה כויתור על referential integrity לטובת פשטות.

---

## 5. שכבת ה-Engine (Backend Math)

### 5.1 חישוב תשואות (`engine/returns.py`)

נשתמש ב-**log-returns**:

```
r_t = ln(P_t / P_{t-1})
```

**למה log-returns ולא תשואות פשוטות:**
- מתחברים: `r_total = sum(r_daily)`.
- קרובות יותר לחלוקה נורמלית — מה ש-Monte Carlo מניח.
- סטנדרט בכל ספרי הלימוד של quant finance.

```python
def daily_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return np.log(prices / prices.shift(1)).dropna()
```

### 5.2 סטטיסטיקה (`engine/statistics.py`)

```python
def mean_returns(returns, periods_per_year=252):
    return returns.mean().values * periods_per_year

def covariance_matrix(returns, periods_per_year=252):
    return returns.cov().values * periods_per_year
```

**μ (mu)** — וקטור N של תשואות שנתיות צפויות (ממוצע היסטורי).
**Σ (sigma)** — מטריצה NxN. אלכסון = variance של נכסים. מחוץ לאלכסון = covariance בין זוגות. **הלב של דיברסיפיקציה.**
**הכפלה ב-252** — ימי מסחר בשנה (סטנדרט תעשייתי).

### 5.3 MVO (`engine/mvo.py`) ⭐

**הניסוח המתמטי:**

```
Maximize:    μᵀw
Subject to:  wᵀΣw ≤ σ_target²
             sum(w) = 1
             0 ≤ w_i ≤ 0.4  לכל i
```

**הסבר על האילוצים:**
1. `wᵀΣw ≤ σ_target²` — variance הפורטפוליו לא חורג מהיעד (השוואה רבועית כדי שהבעיה תהיה quadratic program).
2. `sum(w) = 1` — משקיעים את כל הכסף.
3. `w ≥ 0` — long-only, אין shorting.
4. `w_i ≤ 0.4` — אילוץ דיברסיפיקציה. בלעדיו MVO נוטה לרכז ב-1-2 נכסים.

**הקוד:**

```python
import cvxpy as cp

def solve_mvo(mu, sigma, target_volatility, max_single_weight=0.4):
    n = len(mu)
    w = cp.Variable(n)
    objective = cp.Maximize(mu @ w)
    constraints = [
        cp.sum(w) == 1,
        w >= 0,
        w <= max_single_weight,
        cp.quad_form(w, sigma) <= target_volatility ** 2,
    ]
    problem = cp.Problem(objective, constraints)
    problem.solve()
    if problem.status != cp.OPTIMAL:
        raise ValueError(f"MVO failed: status={problem.status}")
    return w.value
```

**למה cvxpy:** ספרייה אקדמית סטנדרטית (Stanford). ממירה לבעיה conic ושולחת ל-pothור interior-point. אפשר להגן עליה בראיון.

**Artifact למידה נוסף (`engine/mvo_unconstrained.py`):** מימוש closed-form של MVO ללא אילוצים (פיתרון Lagrange) — לא לשימוש בפרודקשן, רק כהוכחת הבנה.

### 5.4 Monte Carlo (`engine/monte_carlo.py`) ⭐

**הרעיון:** דוגמים אלפי מסלולי עתיד אפשריים תחת ההנחה שתשואות יומיות מתחלקות multivariate normal עם μ ו-Σ ההיסטוריים.

**אופטימיזציה חשובה:** במקום לדגום וקטור N-מימדי בכל יום, מנצלים את הזהות `wᵀr ~ Normal(wᵀμ, wᵀΣw)` ודוגמים תשואת פורטפוליו univariate. חיסכון פי N.

```python
def simulate_portfolio(weights, mu_annual, sigma_annual,
                      initial_value, horizon_years,
                      num_paths=10000, seed=42):
    rng = np.random.default_rng(seed)
    days = horizon_years * 252
    
    mu_daily = mu_annual / 252
    sigma_daily = sigma_annual / 252
    
    portfolio_mu = weights @ mu_daily
    portfolio_var = weights @ sigma_daily @ weights
    portfolio_sigma = np.sqrt(portfolio_var)
    
    daily_returns = rng.normal(
        loc=portfolio_mu,
        scale=portfolio_sigma,
        size=(num_paths, days)
    )
    cumulative = np.cumsum(daily_returns, axis=1)
    final_log_return = cumulative[:, -1]
    final_values = initial_value * np.exp(final_log_return)
    return final_values, cumulative
```

מחזירים גם את ה-`cumulative` כדי שיוכלו לחשב timeline של אחוזונים לכל שנה (לטובת ה-fan chart).

### 5.5 מיפוי risk_level → target_volatility

```python
RISK_LEVEL_TO_VOLATILITY = {
    1: 0.05,  # שמרני מאוד (~5% תנודתיות שנתית)
    2: 0.08,
    3: 0.12,  # מאוזן
    4: 0.16,
    5: 0.20,  # אגרסיבי
}
```

הערכים נבחרים כך שיכסו טווח סביר: 5% (תיק שמרני, רוב אג"ח) עד 20% (תיק שמכיל 100% מניות, קרוב לתנודתיות SPY).

---

## 6. שכבת Data (Repositories)

תפקיד: לבודד את הקוד שמדבר עם DB. ה-engine וה-API לא קוראים ל-SQLAlchemy ישירות.

קבצים: `price_repo.py`, `asset_repo.py`, `portfolio_repo.py`, `user_repo.py`, `yfinance_client.py`.

**דוגמה:**

```python
def get_price_history(db: Session, tickers: list[str], years: int = 10) -> pd.DataFrame:
    cutoff = date.today() - timedelta(days=years * 365)
    rows = (
        db.query(Price.date, Price.ticker, Price.close)
          .filter(Price.ticker.in_(tickers))
          .filter(Price.date >= cutoff)
          .all()
    )
    df = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    return df.pivot(index="date", columns="ticker", values="close").dropna()
```

`yfinance_client.py` מבודד תלות חיצונית במקום אחד:

```python
def fetch_price_history(ticker: str, years: int = 10) -> pd.DataFrame:
    data = yf.Ticker(ticker).history(period=f"{years}y")
    if data.empty:
        raise ValueError(f"No data for ticker {ticker}")
    return pd.DataFrame({"close": data["Close"]})
```

---

## 7. שכבת Auth

### 7.1 סיסמאות (`auth/password.py`)

bcrypt דרך passlib:

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain): return pwd_context.hash(plain)
def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)
```

**bcrypt:** salt רנדומי + work factor. גם אם DB דולף, אי אפשר לשחזר סיסמאות בלי כוח רב.

### 7.2 JWT (`auth/jwt.py`)

```python
def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
```

**JWT:** `header.payload.signature`. Stateless — השרת לא שומר sessions ב-DB.
**HS256 (סימטרי):** מתאים כי שרת אחד; אם נצטרך מספר שירותים → RS256.

### 7.3 FastAPI Dependency

```python
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user_id = decode_token(token)
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(401)
    return user
```

כל endpoint שמצריך auth: `user = Depends(get_current_user)` ב-signature.

---

## 8. שכבת API

### 8.1 Endpoints

| Method | Path | תפקיד |
|---|---|---|
| `POST` | `/api/auth/register` | יצירת משתמש + JWT |
| `POST` | `/api/auth/login` | אימות + JWT |
| `GET` | `/api/universe` | רשימת 20 ה-ETFs |
| `POST` | `/api/portfolios/build` | בניית פורטפוליו (MVO + MC) |
| `GET` | `/api/portfolios` | רשימת פורטפוליואים של המשתמש |
| `GET` | `/api/portfolios/{id}` | פורטפוליו ספציפי + fan chart |

### 8.2 דוגמה: `/api/portfolios/build`

```python
@router.post("/build", response_model=PortfolioResponse)
def build_portfolio(
    request: PortfolioBuildRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_prices_available(db, request.tickers)
    
    prices = get_price_history(db, request.tickers, years=10)
    log_returns = daily_log_returns(prices)
    mu = mean_returns(log_returns)
    sigma = covariance_matrix(log_returns)
    
    target_vol = RISK_LEVEL_TO_VOLATILITY[request.risk_level]
    weights = solve_mvo(mu, sigma, target_vol)
    
    final_values, cumulative = simulate_portfolio(
        weights, mu, sigma,
        initial_value=request.amount,
        horizon_years=request.horizon_years,
        seed=42,
    )
    summary = summarize(final_values, cumulative, request.amount, request.horizon_years)
    
    portfolio = save_portfolio(db, user.id, request, weights, summary, ...)
    return PortfolioResponse.from_orm(portfolio)
```

ה-route הוא **אורקסטרציה בלבד** — אין מתמטיקה, אין SQL ישיר.

---

## 9. Frontend (React + Vite + TypeScript)

### 9.1 בחירות ספריות

| ספרייה | למה |
|---|---|
| Vite | מהיר, פשוט, חליף ל-CRA הנטוש |
| axios | interceptors נוחים ל-JWT |
| recharts | React-native, deklarativi |
| tailwindcss | utility-first, פחות CSS לתחזק |
| react-router-dom | routing סטנדרטי |
| zod | אופציונלי — runtime validation של תגובות |

### 9.2 מבנה

```
src/
├── api/                # axios + endpoints
├── auth/               # AuthContext + login/register
├── pages/              # 5 עמודים
├── components/         # 6 קומפוננטות גרפיות
└── types/api.ts
```

### 9.3 State Management

**אין Redux.** רק React Context ל-auth, useState/useEffect לשאר. האפליקציה קטנה מספיק.

### 9.4 אבטחה

- JWT ב-localStorage. חשוף ל-XSS. לפרויקט CV-grade זה מספיק; הסבר ב-README שב-production היה משתמש ב-httpOnly cookies.
- כל בקשה עוברת interceptor שמוסיף את ה-token.
- 401 מהשרת → ניקוי token + redirect ל-/login.

### 9.5 5 העמודים

1. `LoginPage` — טופס פשוט.
2. `RegisterPage` — טופס + validation בסיסי.
3. `BuildPage` — הטופס המלא + תוצאות.
4. `PortfoliosListPage` — טבלה של הפורטפוליואים השמורים.
5. `PortfolioDetailPage` — טעינת פורטפוליו לפי id, הצגת תוצאות.

### 9.6 ה-6 קומפוננטות הגרפיות

| קומפוננטה | מציגה |
|---|---|
| `RiskSlider` | סליידר 1-5 |
| `UniverseSelector` | checkboxes + שדה custom ticker |
| `WeightsTable` | טבלת ticker + אחוז + סכום $ |
| `EfficientFrontierChart` | scatter + נקודה אדומה = הפורטפוליו של המשתמש |
| `FanChart` | ComposedChart עם 3 רצועות אחוזונים |
| `FinalValueHistogram` | histogram + קו VaR |

---

## 10. Testing

### 10.1 פירמידה

```
E2E (1-2):                  full flow דרך הדפדפן (אופציונלי)
API (~10):                  endpoints דרך TestClient
Unit engine + data (~30):   המתמטיקה והרפוזיטוריים
```

### 10.2 דוגמאות בדיקות חשובות

**`test_mvo_target_volatility_respected`** — מאמת שהפיתרון לא חורג מ-σ_target.
**`test_mvo_diversification_constraint_enforced`** — מאמת `w_i ≤ 0.4`.
**`test_monte_carlo_reproducible_with_same_seed`** — אותו seed → אותו תוצאה.
**`test_monte_carlo_mean_close_to_expected`** — ממוצע מסלולים שואף לתוחלת תאורטית.
**`test_register_then_login_returns_token`** — flow auth שלם.
**`test_build_portfolio_full_flow`** — end-to-end אך ללא דפדפן.

### 10.3 fixtures

- `client` — TestClient עם DB ריק.
- `authenticated_client` — עם JWT של משתמש בדיקה.
- `seeded_db` — DB עם 20 ETFs ומחירים סינתטיים (לא מ-yfinance — דטרמיניסטי).

---

## 11. Dev Workflow

### 11.1 Makefile

```makefile
up:        docker compose up -d
down:      docker compose down
logs:      docker compose logs -f backend
test:      docker compose exec backend pytest -v
seed:      docker compose exec backend python -m scripts.seed_universe
migrate:   docker compose exec backend alembic upgrade head
```

### 11.2 7 צעדים מאפס (README)

```bash
git clone <repo> && cd portfolio-builder
cp .env.example .env  # ערוך JWT_SECRET
make up
make migrate
make seed              # ~5 דקות
make test
open http://localhost:5173
```

### 11.3 Seed Script

`scripts/seed_universe.py` — idempotent:
1. כותב 20 ETFs ל-`assets`.
2. מושך 10 שנות מחירים מ-yfinance.
3. כותב ל-`prices`.
4. מדלג על נכסים שכבר קיימים.

### 11.4 CI

GitHub Actions: pytest על Postgres test container + `npm run build` ל-frontend. Badge ירוק ב-README.

---

## 12. היקף ומגבלות

### 12.1 גודל מצופה

| היבט | משוער |
|---|---|
| Backend LoC | ~1500 |
| Frontend LoC | ~1200 |
| טבלאות DB | 4 |
| Endpoints | 7 |
| בדיקות | ~40 |
| מודלים מתמטיים | 2 |

### 12.2 מה **לא** עושים בכוונה

- ❌ אין Celery/Redis/background tasks.
- ❌ אין rebalancing (buy-and-hold בלבד).
- ❌ אין שחזור סיסמה / אימות מייל.
- ❌ אין HRP, אין routing, אין walk-forward backtesting.
- ❌ אין shorting, אין leverage.
- ❌ אין מסחר אמיתי.
- ❌ אין WebSockets / real-time pricing.

**עיקרון:** כל פיצ'ר שלא משרת את שני המודלים המתמטיים — לא נכנס.

### 12.3 הצהרה ל-CV (טיוטה)

> **Portfolio Builder** — פלטפורמת web full-stack לבניית פורטפוליו השקעות בעזרת אופטימיזציית Markowitz mean-variance תחת אילוץ תנודתיות, וסימולציית Monte Carlo להערכת התפלגות תוצאות. בנוי על FastAPI + Postgres + React/TypeScript ב-Docker. כולל JWT auth, schema migrations, ו-CI עם 40+ בדיקות.

---

## 13. נספח — בחירות שנדחו

| הוצע | נדחה כי |
|---|---|
| HRP + MVO | HRP מוסיף שלוש שכבות (clustering, quasi-diag, recursive bisection) שקשה להגן עליהן |
| MVO + CAPM regression | פחות ויזואלי, פחות יקילום ב-UI; CAPM פתוח לאופציה לעתיד |
| Risk Parity במקום MVO | פחות מוכר בתעשייה; MVO הוא הסטנדרט ב-CV |
| Open universe (yfinance only) | inherits את כל הקצוות של yfinance; היברידי קל יותר להגן |
| Pure curated universe (no custom) | פחות מרשים בדמו; הוספנו yfinance במודול מבודד |
| Sessions במקום JWT | sessions דורשות storage; JWT stateless ופשוט יותר |
| Redux | overkill; React Context מספיק |
| Recharts → D3 | D3 imperative וקשה להגן; recharts deklarativi |

---

**סוף המסמך.** ממתין לסקירת המשתמש לפני המעבר לכתיבת תכנית הביצוע.
