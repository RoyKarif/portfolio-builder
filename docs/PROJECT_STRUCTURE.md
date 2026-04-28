# Project Structure — מדריך קבצים מלא

מסמך זה מתאר **כל קובץ** שיהיה בפרויקט אחרי השכתוב. לכל קובץ מפורטים שלושה דברים:

1. **מה** הקובץ עושה.
2. **למה** הוא קיים (מה הוא פותר).
3. **איך** הוא מועיל למערכת.

מסמך זה נועד כך שניתן יהיה לפתוח כל קובץ בפרויקט, להפנות לכאן, ולדעת בדיוק את תפקידו. **אם קובץ קיים בפרויקט אבל לא רשום כאן — זה באג בתיעוד.** אם קובץ רשום כאן אבל לא קיים — עוד לא נוצר.

---

## 1. קבצים בשורש הפרויקט

### `docker-compose.yml`

- **מה:** מגדיר 3 שירותים (`db`, `backend`, `frontend`) ומקשר ביניהם.
- **למה:** Docker Compose מאפשר להריץ סביבת פיתוח מלאה בפקודה אחת (`docker compose up`). זה מבטל את ה"זה עובד אצלי" — כל מי שמשכפל את הריפו מקבל את אותה סביבה.
- **איך מועיל:** משתמשים חדשים (מראיינים, חברים) יכולים להריץ את הפרויקט תוך דקות. כל הסרוויסים מתואמים ב-network פנימי של Docker.

### `.env.example`

- **מה:** דוגמה לקובץ `.env` עם כל משתני הסביבה הנדרשים, אבל בלי ערכים אמיתיים.
- **למה:** `.env` עצמו ב-`.gitignore` (מכיל סודות). `.env.example` בכל זאת ב-Git כדי שכל מי שמשכפל יידע אילו משתנים צריך להגדיר.
- **איך מועיל:** מונע את התקלה הקלאסית של "הריצו את הפרויקט ולא הוגדרו משתנים" — הקובץ הוא תיעוד עצמי.

### `.gitignore`

- **מה:** רשימת קבצים ותיקיות ש-Git יתעלם מהם.
- **למה:** קבצי build, venv, node_modules, סודות, מטמונים — אסור שייכנסו ל-Git.
- **איך מועיל:** שומר על היסטוריית Git נקייה ומונע דליפת סודות.

### `README.md`

- **מה:** תיאור הפרויקט, איך להריץ, מה הוא עושה. הראשון שכל מבקר בריפו רואה.
- **למה:** הפנים של הפרויקט. בלעדיו הריפו נראה לא רציני.
- **איך מועיל:** ה-7 צעדים להרצה מאפס. תיאור המודלים. Badge של CI. הצהרת CV.

### `Makefile`

- **מה:** קיצורי דרך לפקודות מורכבות (`make up`, `make test`, `make seed`).
- **למה:** `docker compose exec backend pytest -v` ארוך לזכור. `make test` קצר.
- **איך מועיל:** הפקודות מתועדות במקום אחד. מי שלא מכיר Docker יכול להריץ.

### `CLAUDE.md`

- **מה:** הוראות עבודה ל-Claude (השפה, איך לכתוב, עקרונות).
- **למה:** מבטיח שכל סשן עתידי עם Claude יעבוד באותו סטנדרט (עברית, הסבר הכל, פשטות).
- **איך מועיל:** דחיסת הניסיון של היום למסמך שעובד גם בעוד חודש.

### `.github/workflows/test.yml`

- **מה:** GitHub Actions workflow שמריץ בדיקות בכל push.
- **למה:** CI מבטיח שכל commit ב-main עובר את הבדיקות. Badge ירוק ב-README = אות איכות.
- **איך מועיל:** מונע regression. מאשר ל-CV שהפרויקט בדוק ומתוחזק.

---

## 2. Backend — תיקיית `backend/`

### 2.1 קבצי תשתית

#### `backend/Dockerfile`

- **מה:** מתאר איך לבנות תמונת Docker של ה-backend (Python 3.11, התקנת requirements, הגדרת CMD).
- **למה:** Docker ה-runtime של ה-backend בכל סביבה (פיתוח, CI, production).
- **איך מועיל:** סביבה זהה תמיד. אין "אצלי עובד אבל אצלך לא".

#### `backend/requirements.txt`

- **מה:** רשימת ספריות Python בגרסאות מדויקות (pinned).
- **למה:** Pinning מבטיח reproducibility — מי שמתקין בעוד שנה מקבל אותן ספריות.
- **איך מועיל:** מבטל הפתעות מעדכוני ספריות. בכל מקום שיש שינוי — מתועד ב-Git.

### 2.2 Migrations — `backend/alembic/`

#### `backend/alembic.ini`

- **מה:** קונפיגורציה של Alembic (DB connection string, paths).
- **למה:** Alembic צריך לדעת איפה ה-DB ואיפה קבצי המיגרציה.
- **איך מועיל:** מרכז הגדרות migration במקום אחד.

#### `backend/alembic/env.py`

- **מה:** "boot" של Alembic — מחבר אותו לבסיס הנתונים ול-models של SQLAlchemy.
- **למה:** Alembic צריך לקרוא את ה-models שלנו כדי להפיק migrations אוטומטית (`alembic revision --autogenerate`).
- **איך מועיל:** מאפשר migrations אוטומטיות במקום לכתוב SQL ידני.

#### `backend/alembic/versions/<timestamp>_initial_schema.py`

- **מה:** המיגרציה הראשונה — יוצרת את 4 הטבלאות (`users`, `assets`, `prices`, `portfolios`) עם כל האילוצים והאינדקסים.
- **למה:** ב-DB ריק, צריך להריץ migration אחת כדי לקבל schema תקף.
- **איך מועיל:** מתעדת את ההיסטוריה של ה-schema. אם ירצה לראות איך ה-DB נראה ב-day-1 — קוראים את הקובץ.

### 2.3 ליבת האפליקציה — `backend/app/`

#### `backend/app/__init__.py`

- **מה:** קובץ ריק שהופך את התיקייה ל-Python package.
- **למה:** Python דורש קובץ זה כדי שהתיקייה תהיה importable.
- **איך מועיל:** מאפשר `from app.engine import mvo` לעבוד.

#### `backend/app/main.py`

- **מה:** נקודת הכניסה של FastAPI. יוצרת את האובייקט `FastAPI()`, מוסיפה middleware, ורושמת את כל ה-routers.
- **למה:** uvicorn צריך משהו לטעון. זה הקובץ.
- **איך מועיל:** ריכוז כל "התרכובת" של האפליקציה במקום אחד — קל לראות מה רץ.

#### `backend/app/config.py`

- **מה:** Pydantic Settings — קוראת משתני סביבה (`DATABASE_URL`, `JWT_SECRET`) ומאמתת אותם.
- **למה:** משתני סביבה הם strings ב-Python; אנחנו רוצים types חזקים. Pydantic נותן את זה + fail-fast (שגיאה בעלייה אם חסר משתנה).
- **איך מועיל:** כל שאר הקוד עושה `from app.config import settings` ומקבל אובייקט typed. אין `os.getenv("...")` מפוזר.

#### `backend/app/db.py`

- **מה:** SQLAlchemy session factory + dependency `get_db()` ל-FastAPI.
- **למה:** כל endpoint צריך session ל-DB. ה-dependency פותח, מספק, וסוגר session אוטומטית.
- **איך מועיל:** מבטל boilerplate בכל endpoint. גם מבטיח שאין דליפת sessions.

### 2.4 Models — `backend/app/models/`

> כל model הוא class של SQLAlchemy שממפה לטבלה ב-DB. אחד-לאחד עם הסכמה ב-spec.

#### `backend/app/models/__init__.py`

- **מה:** מייצא את כל ה-models ואת ה-`Base` המשותף.
- **למה:** Alembic צריך לראות את כל ה-models כדי לגלות שינויים.
- **איך מועיל:** Import אחד מקבל הכל.

#### `backend/app/models/user.py`

- **מה:** class `User` עם `id`, `email`, `password_hash`, `created_at`.
- **למה:** מייצג רשומה בטבלת `users`. SQLAlchemy ממיר אובייקטים → SQL.
- **איך מועיל:** הקוד עובד עם אובייקטים `User` במקום dicts. type-safety וכלי IDE.

#### `backend/app/models/asset.py`

- **מה:** class `Asset` (ticker, name, asset_class, is_curated).
- **למה:** מייצג ETF או custom ticker.
- **איך מועיל:** מקור האמת על מה האפליקציה מכירה.

#### `backend/app/models/price.py`

- **מה:** class `Price` (ticker, date, close).
- **למה:** מחיר יומי של נכס. הזהוי הוא הצירוף `(ticker, date)`.
- **איך מועיל:** הלב של הנתונים — מ-prices מחושבים μ ו-Σ.

#### `backend/app/models/portfolio.py`

- **מה:** class `Portfolio` עם כל השדות מהטבלה (inputs + outputs + mc_seed).
- **למה:** snapshot של בנייה אחת — מה ביקש המשתמש ומה יצא.
- **איך מועיל:** מאפשר למשתמש לחזור לפורטפוליו ישן ולראות אותו בדיוק כמו ביום שיצר אותו.

### 2.5 Schemas — `backend/app/schemas/`

> Pydantic schemas. בניגוד ל-models (DB), schemas הם ייצוג של request/response של ה-API. הם מאמתים קלט ומתעצבים פלט JSON.

#### `backend/app/schemas/__init__.py`

- **מה:** ייצוא של כל ה-schemas.
- **למה:** import נוח.
- **איך מועיל:** קל למצוא איזה schema קיים.

#### `backend/app/schemas/auth.py`

- **מה:** `RegisterRequest`, `LoginRequest`, `TokenResponse`.
- **למה:** מגדיר את ה-payloads של `/api/auth/register` ו-`/login`.
- **איך מועיל:** FastAPI מאמת אוטומטית — מייל לא תקין? 422 לפני שהקוד שלי רץ.

#### `backend/app/schemas/portfolio.py`

- **מה:** `PortfolioBuildRequest` (amount, risk_level, horizon, tickers), `PortfolioResponse` (כל מה שחוזר ל-frontend).
- **למה:** חוזה ה-API. ה-frontend ב-TypeScript משכפל את אותם types.
- **איך מועיל:** validation של inputs (`risk_level: int = Field(ge=1, le=5)`) + serialization של outputs (JSON עקבי).

### 2.6 Data Layer — `backend/app/data/`

> שכבת גישה לנתונים. כל מודול הוא **repository** שמרכז גישה ל-entity מסוים. ה-API ו-engine **לא** קוראים ל-SQLAlchemy ישירות.

#### `backend/app/data/__init__.py`

- **מה:** ייצוא ה-repositories.
- **למה:** import נוח.

#### `backend/app/data/user_repo.py`

- **מה:** `create_user`, `get_user_by_email`, `get_user_by_id`.
- **למה:** מבודד SQL של משתמשים במקום אחד. ה-API לא יודע לכתוב queries.
- **איך מועיל:** קל לבדוק במנותק (mock-ing פשוט). שינוי ב-DB משנה רק את הקובץ הזה.

#### `backend/app/data/asset_repo.py`

- **מה:** `get_curated_assets`, `get_asset_by_ticker`, `create_asset`.
- **למה:** מבודד גישה ל-`assets`.
- **איך מועיל:** ה-API ל-`/universe` קורא לפונקציה אחת.

#### `backend/app/data/price_repo.py`

- **מה:** `get_price_history(tickers, years) -> pd.DataFrame`, `bulk_insert_prices`.
- **למה:** הפונקציה החשובה ביותר ב-data layer. ממירה SQL ל-DataFrame בפורמט שה-engine מצפה.
- **איך מועיל:** ה-engine מקבל DataFrame "נקי" ולא צריך לדעת על SQL.

#### `backend/app/data/portfolio_repo.py`

- **מה:** `save_portfolio`, `get_portfolio`, `list_user_portfolios`.
- **למה:** מבודד גישה ל-`portfolios`.
- **איך מועיל:** עקביות בקריאה/כתיבה של פורטפוליואים.

#### `backend/app/data/yfinance_client.py`

- **מה:** עוטף את ספריית `yfinance`. פונקציה אחת: `fetch_price_history(ticker, years) -> pd.DataFrame`.
- **למה:** תלות חיצונית מסוכנת — יש לה edge cases. ריכוז ב-מודול אחד = שטח התקפה ידוע.
- **איך מועיל:** אם yfinance ישתנה (או נחליף ל-Alpha Vantage) — שינוי במקום אחד.

### 2.7 Engine — `backend/app/engine/` ⭐ הלב של הפרויקט

> מתמטיקה טהורה. **בלי תלות ב-DB או HTTP.** מקבל arrays/DataFrames, מחזיר arrays/dicts.

#### `backend/app/engine/__init__.py`

- **מה:** ייצוא הפונקציות הראשיות.

#### `backend/app/engine/returns.py`

- **מה:** פונקציה `daily_log_returns(prices: pd.DataFrame) -> pd.DataFrame`.
- **למה:** ממיר מחירים ל-log-returns יומיות. log-returns מתחברים ב-summation וקרובים יותר לחלוקה נורמלית מ-simple returns.
- **איך מועיל:** קלט בסיסי לכל חישוב סטטיסטי שבא אחר כך.

#### `backend/app/engine/statistics.py`

- **מה:** `mean_returns(returns) -> np.ndarray` (μ), `covariance_matrix(returns) -> np.ndarray` (Σ). שתיהן מכפילות ב-252 ל-annualization.
- **למה:** שני הפרמטרים הסטטיסטיים שמניעים גם MVO וגם Monte Carlo.
- **איך מועיל:** אם השיטה לאמדן μ/Σ תשתנה (למשל shrinkage estimator) — שינוי במקום אחד.

#### `backend/app/engine/mvo.py` ⭐

- **מה:** `solve_mvo(mu, sigma, target_volatility) -> weights`. פותר Quadratic Program עם cvxpy.
- **למה:** המודל המתמטי המרכזי. מוצא משקלות שמקסמות תשואה תחת אילוץ תנודתיות.
- **איך מועיל:** הפלט הזה הוא ה-`weights` שהמשתמש רואה.

#### `backend/app/engine/mvo_unconstrained.py`

- **מה:** Closed-form solution של MVO ללא אילוצים, באמצעות Lagrange multipliers.
- **למה:** **artifact למידה**. לא בשימוש בפרודקשן. מוכיח שאני מבין את הבסיס המתמטי, לא רק "קורא ל-cvxpy".
- **איך מועיל:** נכס ל-CV ולראיון. מאפשר להראות נוסחה על הלוח.

#### `backend/app/engine/monte_carlo.py` ⭐

- **מה:** `simulate_portfolio(weights, mu, sigma, initial_value, years, num_paths, seed) -> (final_values, cumulative)`. דגימה מ-multivariate normal, חישוב מסלולים.
- **למה:** המודל המתמטי השני. מציג התפלגות תוצאות אפשריות.
- **איך מועיל:** ה-fan chart שהמשתמש רואה. גם מספק VaR.

### 2.8 Auth — `backend/app/auth/`

#### `backend/app/auth/__init__.py`

- **מה:** ייצוא של פונקציות auth.

#### `backend/app/auth/password.py`

- **מה:** `hash_password`, `verify_password`. wrapper ל-passlib עם bcrypt.
- **למה:** **לעולם לא לאחסן סיסמאות בטקסט.** bcrypt עם salt מובנה ו-work factor.
- **איך מועיל:** גם אם DB דולף, התוקף לא משחזר סיסמאות בקלות.

#### `backend/app/auth/jwt.py`

- **מה:** `create_access_token(user_id) -> str`, `decode_token(str) -> int`.
- **למה:** JWT מאפשר auth stateless — השרת לא שומר sessions. הסוד נמצא רק אצלו.
- **איך מועיל:** scaling קל (כל שרת יכול לאמת את אותו token), אין צורך ב-DB lookup לכל בקשה.

#### `backend/app/auth/dependencies.py`

- **מה:** `get_current_user` — FastAPI dependency שמפענח את ה-token ומחזיר את ה-User.
- **למה:** כל endpoint שדורש auth: `user = Depends(get_current_user)`. בלי קוד חוזר.
- **איך מועיל:** הפרדה נקייה בין endpoints ציבוריים למוגנים.

### 2.9 API — `backend/app/api/`

#### `backend/app/api/__init__.py`

- **מה:** ייצוא ה-routers.

#### `backend/app/api/auth_routes.py`

- **מה:** `POST /api/auth/register`, `POST /api/auth/login`.
- **למה:** האנדפוינטים שמייצרים ומחזירים JWT.
- **איך מועיל:** ללא endpoints אלה אין כניסה לאפליקציה.

#### `backend/app/api/universe_routes.py`

- **מה:** `GET /api/universe` — מחזיר את 20 ה-ETFs.
- **למה:** ה-frontend צריך לרנדר checkboxes. צריך לדעת מה ביקום.
- **איך מועיל:** ה-frontend לא משכפל את הרשימה — מקבל מהשרת.

#### `backend/app/api/portfolio_routes.py`

- **מה:** `POST /api/portfolios/build`, `GET /api/portfolios`, `GET /api/portfolios/{id}`.
- **למה:** ה-endpoints המרכזיים של האפליקציה.
- **איך מועיל:** כל הזרימה (input → MVO → MC → save → return) תחת קובץ אחד נקי.

### 2.10 Scripts — `backend/scripts/`

#### `backend/scripts/seed_universe.py`

- **מה:** סקריפט שמריצים פעם אחת בהקמה. כותב 20 ה-ETFs ל-`assets`, מושך מ-yfinance 10 שנים, כותב ל-`prices`.
- **למה:** ב-DB ריק, אין נתונים. בלי הסקריפט ה-MVO ו-MC לא יכולים לרוץ.
- **איך מועיל:** idempotent — אפשר להריץ פעמיים. מציג התקדמות. כישלון בנכס אחד לא מפיל את כולו.

### 2.11 Tests — `backend/tests/`

#### `backend/tests/conftest.py`

- **מה:** pytest fixtures — `db`, `client`, `authenticated_client`, `seeded_db`.
- **למה:** קוד חוזר בבדיקות (יצירת DB, יצירת token) מרוכז.
- **איך מועיל:** בדיקות חדשות מקבלות fixtures בחתימה — אין boilerplate.

#### `backend/tests/test_engine/test_returns.py`

- **מה:** בדיקות `daily_log_returns` (קלט ידוע → פלט ידוע).
- **למה:** הפונקציה הראשונה בשרשרת — אם היא שגויה, הכל שגוי.
- **איך מועיל:** ביטחון שהבסיס תקין.

#### `backend/tests/test_engine/test_statistics.py`

- **מה:** בדיקות `mean_returns` ו-`covariance_matrix`.
- **למה:** אימות שה-annualization ב-252 נכון.
- **איך מועיל:** מנה אם פעם נחליף ל-365 או ל-monthly.

#### `backend/tests/test_engine/test_mvo.py`

- **מה:** ~5 בדיקות: target_volatility מוכבד, אילוץ דיברסיפיקציה, sum=1, w≥0, מעדיף תשואה גבוהה.
- **למה:** **המודל הראשי.** כל באג כאן הוא קטסטרופה.
- **איך מועיל:** רגרסיה מסודרת אם נתקן/נשנה משהו.

#### `backend/tests/test_engine/test_monte_carlo.py`

- **מה:** ~5 בדיקות: reproducibility (אותו seed), ממוצע קרוב לתאוריה, התפלגות אחוזונים.
- **למה:** **המודל השני.** סטטיסטיקה רגישה לבאגים זעירים (יחידות יומי/שנתי).
- **איך מועיל:** מבחן שמהזמן.

#### `backend/tests/test_data/test_price_repo.py`

- **מה:** קריאה וכתיבה של מחירים, פיווט נכון של DataFrame.
- **למה:** המודול מתרגם בין SQL ל-pandas — נקודה רגישה.
- **איך מועיל:** מבטיח ש-engine מקבל פורמט עקבי.

#### `backend/tests/test_api/test_auth.py`

- **מה:** רישום, התחברות, שגיאת סיסמה, שגיאת token.
- **למה:** auth — אם שבור, אף אחד לא נכנס.
- **איך מועיל:** ביטחון בכניסה למערכת.

#### `backend/tests/test_api/test_portfolio.py`

- **מה:** flow שלם של בניית פורטפוליו, שמירה, רשימה.
- **למה:** integration test — המסלול הכי חשוב מבחינת המשתמש.
- **איך מועיל:** מבטיח שכל השכבות מתחברות נכון.

---

## 3. Frontend — תיקיית `frontend/`

### 3.1 קבצי תשתית

#### `frontend/Dockerfile`

- **מה:** Multi-stage build: Node לבילד, nginx להגשה (production). dev mode = vite dev server ישירות.
- **למה:** production-grade serving של static files.
- **איך מועיל:** באותו `docker compose up` ה-frontend עולה גם ב-dev וגם בעת build.

#### `frontend/package.json`

- **מה:** רשימת dependencies (`react`, `axios`, `recharts`...) + scripts (`dev`, `build`, `test`).
- **למה:** npm צריך אותו.
- **איך מועיל:** Pin של versions = reproducibility.

#### `frontend/package-lock.json`

- **מה:** נעילה מדויקת של כל ה-dependencies (כולל nested).
- **למה:** מבטיח ש-`npm ci` יותקן את אותן ספריות בכל מקום.
- **איך מועיל:** מבטל "אצלי עובד" של הספריות.

#### `frontend/vite.config.ts`

- **מה:** קונפיגורציה של Vite — proxy ל-`/api` ל-backend, alias ל-`@/` → `src/`.
- **למה:** ב-dev, ה-frontend ב-:5173 וה-backend ב-:8000. proxy מאפשר לקרוא `/api/...` מהדפדפן בלי CORS.
- **איך מועיל:** development חלק.

#### `frontend/tsconfig.json` + `frontend/tsconfig.app.json` + `frontend/tsconfig.node.json`

- **מה:** קונפיגורציה של TypeScript — strict mode, targets, paths.
- **למה:** TS דורש קונפיגורציה. `strict: true` חיוני — מבטיח type safety אמיתי.
- **איך מועיל:** תופס באגים בזמן קומפילציה במקום בזמן ריצה.

#### `frontend/index.html`

- **מה:** ה-HTML הראשי. רק `<div id="root"></div>` ו-`<script src="/src/main.tsx">`.
- **למה:** SPA — דף אחד, React מנהל את הכל.
- **איך מועיל:** Vite מזריק את הקוד הזה.

#### `frontend/eslint.config.js`

- **מה:** כללי ESLint.
- **למה:** עקביות סגנון, תפיסת באגים נפוצים.
- **איך מועיל:** קוד נראה אותו דבר בכל מקום, מקטין friction בעבודה משותפת.

### 3.2 ליבת האפליקציה — `frontend/src/`

#### `frontend/src/main.tsx`

- **מה:** נקודת הכניסה. Mount של `<App />` ב-DOM.
- **למה:** React חייב mount.
- **איך מועיל:** הקובץ היחיד שמתעסק עם React DOM API.

#### `frontend/src/App.tsx`

- **מה:** Root component. עוטף ב-`<AuthProvider>`, ב-`<BrowserRouter>`, מגדיר את כל ה-routes.
- **למה:** מקום אחד שמראה את "מפת" האפליקציה.
- **איך מועיל:** קל להבין מה האפליקציה מכילה — רק לפתוח App.tsx.

#### `frontend/src/index.css`

- **מה:** import של tailwindcss + global styles בסיסיים.
- **למה:** Tailwind utility-first — רוב ה-styling inline ב-className.
- **איך מועיל:** פחות קבצי CSS לתחזק, פחות בעיות specificity.

### 3.3 API Client — `frontend/src/api/`

#### `frontend/src/api/client.ts`

- **מה:** instance של axios + interceptors (request: הוסף JWT, response: 401 → redirect ל-login).
- **למה:** מרכז את כל הקונפיגורציה של HTTP במקום אחד.
- **איך מועיל:** כל בקשה אוטומטית כוללת את ה-token. שגיאות auth מטופלות גלובלית.

#### `frontend/src/api/auth.ts`

- **מה:** פונקציות `login`, `register` שעוטפות `apiClient`.
- **למה:** הפרדה לפי domain. קל למצוא איפה auth.
- **איך מועיל:** components קוראים `await api.auth.login(...)`, לא `apiClient.post(...)`.

#### `frontend/src/api/portfolio.ts`

- **מה:** `build`, `list`, `get` של פורטפוליואים.
- **למה:** כנ"ל — domain-specific.

#### `frontend/src/api/universe.ts`

- **מה:** `getCurated`, `addCustom`.
- **למה:** מנהל את היקום מצד ה-frontend.

#### `frontend/src/api/index.ts`

- **מה:** ייצוא נוח: `export const api = { auth, portfolio, universe }`.
- **למה:** import אחד בקומפוננטות.
- **איך מועיל:** `import { api } from '@/api'`.

### 3.4 Auth — `frontend/src/auth/`

#### `frontend/src/auth/AuthContext.tsx`

- **מה:** React Context שמחזיק את ה-user ו-token. שמירה/טעינה מ-localStorage.
- **למה:** state גלובלי של auth דרוש בכל מקום.
- **איך מועיל:** `const { user, login, logout } = useAuth()` בכל component.

#### `frontend/src/auth/LoginPage.tsx`

- **מה:** טופס התחברות (email + password) → קורא ל-`api.auth.login`.
- **למה:** המשתמש צריך מסך התחברות.
- **איך מועיל:** UX פשוט וברור.

#### `frontend/src/auth/RegisterPage.tsx`

- **מה:** טופס רישום (email + password + confirm) → `api.auth.register`.
- **למה:** משתמש חדש.
- **איך מועיל:** validation בסיסי בצד הלקוח לפני קריאה ל-API.

#### `frontend/src/auth/ProtectedRoute.tsx`

- **מה:** Component שעוטף routes שדורשים auth. אם אין token → `<Navigate to="/login" />`.
- **למה:** שחור-לבן — או נכנסת או לא.
- **איך מועיל:** אין קוד חוזר בכל page.

### 3.5 Pages — `frontend/src/pages/`

#### `frontend/src/pages/BuildPage.tsx`

- **מה:** **הדף המרכזי.** הטופס המלא + הצגת תוצאות.
- **למה:** המקום שבו המשתמש בונה את הפורטפוליו.
- **איך מועיל:** orchestration של 6 הקומפוננטות הגרפיות.

#### `frontend/src/pages/PortfoliosListPage.tsx`

- **מה:** טבלה של פורטפוליואים שהמשתמש שמר. כל שורה לחיצה → דף פרטים.
- **למה:** ניווט להיסטוריה.
- **איך מועיל:** המשתמש לא צריך לזכור מה בנה.

#### `frontend/src/pages/PortfolioDetailPage.tsx`

- **מה:** מציג פורטפוליו ספציפי לפי id ב-URL.
- **למה:** אפשר לחזור לפורטפוליו ישן ולראות אותו.
- **איך מועיל:** משתמש ב-`mc_seed` השמור → אותו fan chart בדיוק.

### 3.6 Components — `frontend/src/components/`

#### `frontend/src/components/RiskSlider.tsx`

- **מה:** סליידר 1-5 + label דינמי ("שמרני" / "מאוזן" / "אגרסיבי").
- **למה:** קלט פרימיטיבי שמופיע ב-BuildPage.
- **איך מועיל:** UX אינטואיטיבי.

#### `frontend/src/components/UniverseSelector.tsx`

- **מה:** רשימת checkboxes של 20 ה-ETFs (מסומנים כברירת מחדל) + שדה "הוסף ticker".
- **למה:** המשתמש בוחר על מה לבנות.
- **איך מועיל:** מנהל את הלוגיקה של include/exclude/custom.

#### `frontend/src/components/AmountInput.tsx`

- **מה:** input מספרי עם פורמט של דולרים.
- **למה:** סכום ההשקעה.

#### `frontend/src/components/HorizonInput.tsx`

- **מה:** input מספרי לאופק זמן (1-30 שנים).

#### `frontend/src/components/WeightsTable.tsx`

- **מה:** טבלה עם ticker, אחוז, סכום ב-$.
- **למה:** הצגה ברורה של תוצאות MVO.
- **איך מועיל:** המשתמש מבין מיד מה הוא קונה.

#### `frontend/src/components/EfficientFrontierChart.tsx`

- **מה:** Scatter plot של frontier (תנודתיות-תשואה), עם נקודה אדומה = הפורטפוליו של המשתמש.
- **למה:** מציג ויזואלית את החלטת ה-MVO.
- **איך מועיל:** מראיין רואה ויזואלית "אני מבין mean-variance".

#### `frontend/src/components/FanChart.tsx`

- **מה:** ComposedChart של recharts. 3 רצועות (5-95%, 25-75%) + קו חציון.
- **למה:** התוצאה הוויזואלית של Monte Carlo.
- **איך מועיל:** הגרף הכי מרשים בדמו.

#### `frontend/src/components/FinalValueHistogram.tsx`

- **מה:** היסטוגרמה של ערכי-סוף + קו אנכי על VaR.
- **למה:** מציג סיכון בצורה אחרת.
- **איך מועיל:** משלים את ה-fan chart — שני זוויות על אותם נתונים.

#### `frontend/src/components/StatsPanel.tsx`

- **מה:** 3 כרטיסי סטטיסטיקה: תשואה צפויה, תנודתיות, Sharpe.
- **למה:** מספרים יבשים שצריך להציג בצורה נקייה.

#### `frontend/src/components/ErrorBanner.tsx`

- **מה:** הצגת שגיאה אחידה.
- **למה:** UX עקבי לטיפול בשגיאות.

### 3.7 Types — `frontend/src/types/`

#### `frontend/src/types/api.ts`

- **מה:** TypeScript types של כל request/response (`PortfolioBuildRequest`, `PortfolioResponse` וכו').
- **למה:** משכפל את ה-Pydantic schemas מהbackend, אבל ב-TS.
- **איך מועיל:** type safety בכל הfrontend. שינוי ב-API → שינוי כאן → שגיאות קומפיילציה במקומות שצריך לעדכן.

---

## 4. סיכום כמותי

| קטגוריה | מספר קבצים מצופה |
|---|---|
| Root config | ~7 |
| Backend infra | ~3 |
| Backend models | 5 |
| Backend schemas | 3 |
| Backend data | 6 |
| Backend engine | 6 |
| Backend auth | 4 |
| Backend api | 4 |
| Backend scripts | 1-2 |
| Backend tests | ~10 |
| Frontend infra | ~7 |
| Frontend api | 5 |
| Frontend auth | 4 |
| Frontend pages | 3 |
| Frontend components | ~10 |
| Frontend types | 1-2 |
| **סה"כ** | **~80 קבצים** |

---

## 5. עיקרון מנחה

**אם פתחת קובץ ולא ברור לך תפקידו — חזור לכאן.**

אם המסמך לא מסביר טוב מספיק — זה באג בתיעוד שצריך לתקן.
