# Claude Working Guide — Portfolio Builder

הוראות עבודה לכל סשן של Claude בפרויקט הזה. **חובה לקרוא לפני כל עבודה.**

---

## 1. הקשר הפרויקט

זה **שכתוב מלא** של Portfolio Builder. המטרה היחידה: פרויקט שניתן להגן עליו ב-100% בראיון עבודה, מ-DB עד ה-frontend.

**שני מודלים מתמטיים בלב המערכת:**
- Markowitz Mean-Variance Optimization (MVO)
- Monte Carlo simulation

**Stack:** FastAPI + PostgreSQL + React/Vite + TypeScript + Docker.

**מסמכים מרכזיים:**
- ה-spec המלא: [docs/superpowers/specs/2026-04-28-portfolio-builder-rewrite-design.md](docs/superpowers/specs/2026-04-28-portfolio-builder-rewrite-design.md)
- מבנה קבצים מלא עם הסבר על כל קובץ: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

---

## 2. כללי תקשורת — חובה

### 2.1 שפה

| היכן | שפה |
|---|---|
| תקשורת עם המשתמש (טקסט, שאלות, סיכומים) | **עברית** |
| קוד (משתנים, פונקציות, תגובות בקוד) | **אנגלית** |
| מסמכים (specs, plans, README, CLAUDE.md) | **עברית** |
| Commit messages | **אנגלית** (קונבנציה תעשייתית) |
| מונחים טכניים בתוך עברית | **לא לתרגם** (MVO, JWT, FastAPI, covariance matrix וכו') |

### 2.2 הסבר מלא — חובה

**כל קוד שנכתב חייב להיות מלווה בהסבר. בלי יוצא מן הכלל.**

ההסבר חייב לכלול שלושה דברים:

1. **מה** הקוד עושה (השורה, הפונקציה, הקובץ).
2. **למה** הוא כתוב ככה (לעומת אלטרנטיבות).
3. **איך** הוא מועיל למערכת.

זה חל על:
- כל שורת SQL — להסביר את העמודה, הסוג, האילוץ, האינדקס.
- כל פונקציה Python — מטרה, חתימה, איך משתמשים בה.
- כל בחירת ספרייה — למה הספרייה הזאת ולא אחרת.
- כל החלטת ארכיטקטורה — אלטרנטיבות שנשקלו.
- כל נוסחה מתמטית — הניסוח, המשתנים, ההיגיון.
- כל באג שתוקן — הגורם, הפיתרון, איך זיהינו.

**אל תניח רקע.** אם נדרש מושג בסיסי (covariance, JWT, foreign key, dependency injection) — להסביר בקצרה.

### 2.3 השמטה אסורה

- ❌ אסור לכתוב קוד "כי כך מקובל" בלי הסבר.
- ❌ אסור לדלג על הסברים אפילו אם זה "ברור".
- ❌ אסור לסמוך על "המשתמש יבין מהקוד".
- ❌ אסור להוסיף ספרייה בלי לתעד את הצדקתה.

---

## 3. עקרונות עבודה

### 3.1 בעלות מלאה (Ownership)

- כל החלטה — לתעד.
- כל ספרייה חיצונית — להסביר ולהצדיק.
- אין "magic" — אם משהו מסתורי, להסביר עד שהוא לא מסתורי.

### 3.2 פשטות > "מקצועיות"

- תיק שלא צריך > תיק "כי תמיד עושים".
- אם feature לא משרת את MVO או Monte Carlo — לא נכנס לפרויקט.
- מותר לכתוב 30 שורות "צעירות" בלי דפוסים מורכבים, אם הן עובדות וברורות.

### 3.3 שכבות מבודדות (Dependency Inversion)

- ה-**engine** (מתמטיקה) **לא** יודע על HTTP או על DB. מקבל `np.ndarray`/`pd.DataFrame`, מחזיר `np.ndarray`/`dict`.
- ה-**data layer** (repositories) **לא** יודע על HTTP. מקבל `Session`, מחזיר entities.
- ה-**API** **לא** מכיל מתמטיקה ולא SQL ישיר. רק orchestration.

זה מה שמאפשר לבדוק כל שכבה במנותק.

### 3.4 גודל קבצים

- קובץ Python: עד ~150 שורות.
- קומפוננטת React: עד ~100 שורות.
- אם חורג → לפצל למודולים קטנים יותר.

---

## 4. Git Workflow

### 4.1 Commits — קטן ומהוקצע

- **משימה אחת = קומיט אחד.** לא לערבב.
- ההודעה באנגלית, פורמט Conventional Commits:
  - `feat(engine): MVO solver with cvxpy`
  - `fix(api): handle missing ticker in build endpoint`
  - `docs(spec): clarify volatility mapping`
  - `test(monte-carlo): reproducibility with same seed`
  - `chore(deps): pin numpy to 1.26`
- Types נפוצים: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

### 4.2 Branch

- Branch ייעודי לשכתוב (`rewrite/clean-slate` או דומה).
- הקוד הישן נשמר בענפים אחרים — לא נמחק.

### 4.3 בדיקה לפני קומיט

לפני כל `git commit`:
- ✅ הבדיקות הרלוונטיות עוברות.
- ✅ אין warnings של types/lint.
- ✅ ה-feature שעובדים עליו עובד פעם אחת ידנית (אם רלוונטי).

---

## 5. Testing

- כל פונקציה ב-`engine/` → לפחות בדיקה אחת.
- כל endpoint → בדיקה אחת מינימום (success + auth).
- בדיקות **לא תלויות ברשת** — fixtures דטרמיניסטיות, mocking של yfinance.
- מטרה: כל הבדיקות רצות תוך 30 שניות.

---

## 6. זיכרון ארוך-טווח (Auto Memory)

זיכרון של Claude שמור ב:
`/Users/roeykarif/.claude/projects/-Users-roeykarif-Portfolio-Builder/memory/`

כללי השפה (עברית) ו"הסבר הכל" שמורים שם — חלים אוטומטית בכל סשן.

---

## 7. נסיבות מיוחדות

- אם הקוד הישן (לפני השכתוב) דרוש כהפניה — אפשר להסתכל בענפים אחרים, לא להעתיק עיוור.
- אם נדרש להוסיף ספרייה שלא ב-`requirements.txt`/`package.json` — קודם להסביר למה, אז להוסיף.
- בעיות חיצוניות (yfinance נופל, internet לא עובד) — להציג למשתמש, לא לעקוף בשקט.
