# Portfolio Builder

פלטפורמת web full-stack לבניית פורטפוליו השקעות בעזרת שני מודלים מתמטיים:

1. **Markowitz Mean-Variance Optimization (MVO)** — מציאת המשקלות שמקסמות תשואה צפויה תחת אילוץ תנודתיות.
2. **Monte Carlo simulation** — הדמיית אלפי מסלולי עתיד אפשריים להערכת התפלגות התוצאות.

המטרה: פרויקט שניתן להגן עליו ב-100% — מ-DB ועד ה-UI.

---

## Stack

- **Backend:** FastAPI (Python 3.11) + SQLAlchemy + cvxpy + numpy
- **Frontend:** React 18 + Vite + TypeScript + Tailwind + recharts
- **Database:** PostgreSQL 16
- **Auth:** JWT (HS256) + bcrypt
- **Infra:** Docker Compose

---

## הרצה מהירה (7 צעדים)

```bash
# 1. שכפול
git clone <repo> && cd portfolio-builder

# 2. הגדרת משתני סביבה
cp .env.example .env
# ערוך .env והחלף JWT_SECRET (מומלץ: openssl rand -hex 32)

# 3. הרמת הסטאק
make up

# 4. הרצת migrations (יוצר את 4 הטבלאות)
make migrate

# 5. זריעת היקום (20 ETFs + 10 שנות מחירים מ-yfinance, ~5 דקות)
make seed

# 6. בדיקות
make test

# 7. פתיחת הדפדפן
open http://localhost:5173
```

---

## תיעוד

- **כללי עבודה ל-Claude:** [CLAUDE.md](CLAUDE.md)
- **ה-spec המלא:** [docs/superpowers/specs/2026-04-28-portfolio-builder-rewrite-design.md](docs/superpowers/specs/2026-04-28-portfolio-builder-rewrite-design.md)
- **מבנה קבצים מלא עם הסבר על כל קובץ:** [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

---

## פקודות שימושיות

```bash
make up         # הפעלת כל השירותים
make down       # כיבוי
make logs       # מעקב אחר logs של ה-backend
make test       # הרצת הבדיקות
make seed       # זריעת DB
make migrate    # הרצת migrations
make psql       # shell של Postgres
make help       # רשימת כל הפקודות
```

---

## רישיון

פרויקט אישי לצורכי למידה. אין מחויבויות, אין אחריות, אין יעוץ פיננסי.
