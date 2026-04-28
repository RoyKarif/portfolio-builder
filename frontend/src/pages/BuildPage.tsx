// Main page: friendly form on top, results below after submission.
//
// Design principle: the user gives 4 inputs (amount+horizon, risk,
// investment scope, country). Asset selection is hidden behind an
// "advanced" link — most users don't know what tickers are.

import { useEffect, useState, useMemo, type FormEvent, type ReactNode } from "react";
import { Layout } from "../components/Layout";
import { RiskSlider } from "../components/RiskSlider";
import { UniverseSelector } from "../components/UniverseSelector";
import { ResultsPanel } from "../components/ResultsPanel";
import { api } from "../api";
import type { Asset, PortfolioResponse } from "../types/api";

// Plain-language description of what each risk level means.
const RISK_DESCRIPTIONS: Record<number, string> = {
  1: "תיק שמרני מאוד: רוב הכסף באג\"ח ומזומן. תנודות קטנות, תשואה צנועה.",
  2: "תיק שמרני: בעיקר אג\"ח עם אחוז קטן של מניות. תנודתיות נמוכה.",
  3: "תיק מאוזן: שילוב קלאסי של מניות ואג\"ח. מתאים לרוב המשקיעים לטווח בינוני-ארוך.",
  4: "תיק אגרסיבי מתון: רוב הכסף במניות, עם כרית בטחון של אג\"ח.",
  5: "תיק אגרסיבי: כמעט הכל במניות. תשואה צפויה גבוהה, אבל תנודות חזקות.",
};

// Country → short note about access/tax considerations.
type Country = "israel" | "us" | "europe" | "other";

const COUNTRY_OPTIONS: { value: Country; label: string }[] = [
  { value: "israel", label: "ישראל" },
  { value: "us", label: "ארה\"ב" },
  { value: "europe", label: "אירופה (EU/UK)" },
  { value: "other", label: "אחר" },
];

const COUNTRY_NOTES: Record<Country, string> = {
  israel:
    "כל ה-ETFs האמריקאיים זמינים דרך ברוקרים ישראליים. שים לב למס על דיבידנדים זרים (15%) ולמס עיזבון אמריקאי על פוזיציות שערכן מעל $60K.",
  us:
    "אין הגבלות נוספות — גישה מלאה לכל ה-ETFs האמריקאיים.",
  europe:
    "תקנות PRIIPs עלולות להגביל גישה ל-ETFs אמריקאיים. ברוקרים אירופאיים בדרך כלל ידרשו ETFs בתצורת UCITS (אירופאיים) במקום אמריקאיים. רוב ה-ETFs ברשימה כאן הם אמריקאיים.",
  other:
    "ייתכנו הגבלות גישה תלויות-מדינה. בדוק עם הברוקר שלך אילו ETFs אמריקאיים זמינים לך.",
};

// What the "investment scope" radio means.
type Scope = "all" | "equity_only";

export function BuildPage() {
  const [universe, setUniverse] = useState<Asset[] | null>(null);
  const [universeError, setUniverseError] = useState<string | null>(null);

  const [amount, setAmount] = useState(10000);
  const [risk, setRisk] = useState(3);
  const [horizon, setHorizon] = useState(10);
  const [scope, setScope] = useState<Scope>("all");
  const [country, setCountry] = useState<Country>("israel");

  // Tickers selected for the build. Default = entire universe.
  // Modified only via the advanced customizer.
  const [tickers, setTickers] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [result, setResult] = useState<PortfolioResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load curated universe.
  useEffect(() => {
    api.universe.getCurated()
      .then((u) => {
        setUniverse(u);
        setTickers(u.map((a) => a.ticker));
      })
      .catch(() => {
        setUniverseError("לא הצלחתי לטעון את רשימת הנכסים מהשרת.");
      });
  }, []);

  // The actual list of tickers that will go to the backend, after
  // applying the scope filter.
  const effectiveTickers = useMemo(() => {
    if (universe === null) return [];
    if (scope === "all") return tickers;
    // "equity_only": keep only those whose asset_class is 'equity'.
    const equityTickers = new Set(
      universe.filter((a) => a.asset_class === "equity").map((a) => a.ticker),
    );
    return tickers.filter((t) => equityTickers.has(t));
  }, [tickers, scope, universe]);

  const equityCountInUniverse = useMemo(
    () => universe?.filter((a) => a.asset_class === "equity").length ?? 0,
    [universe],
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (universe === null) {
      setError("הנתונים עדיין נטענים. רגע אחד...");
      return;
    }
    if (universe.length === 0) {
      setError(
        "המערכת ריקה מנכסים. כנראה שהזרעה עדיין לא רצה. " +
        "הרץ בטרמינל: make seed (או ניסה seed עם synthetic data).",
      );
      return;
    }
    if (effectiveTickers.length < 2) {
      setError(
        "פחות מ-2 נכסים זמינים אחרי הסינונים שבחרת. שנה את ההגדרות (למשל, הסר את אילוץ \"רק מניות\").",
      );
      return;
    }

    setSubmitting(true);
    setResult(null);
    try {
      const portfolio = await api.portfolio.build({
        amount,
        risk_level: risk,
        horizon_years: horizon,
        tickers: effectiveTickers,
      });
      setResult(portfolio);
      setTimeout(() => {
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        ?? "שגיאה בבניית הפורטפוליו";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const universeReady = universe !== null && universe.length > 0;
  const customCount = universe
    ? tickers.filter((t) => !universe.some((a) => a.ticker === t)).length
    : 0;
  const excludedCount = universe
    ? universe.filter((a) => !tickers.includes(a.ticker)).length
    : 0;

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-3xl font-bold">בנה פורטפוליו השקעות</h1>
        <p className="text-gray-600 mt-2 leading-relaxed">
          הכלי משתמש במודל המתמטי של מרקוביץ' (Mean-Variance Optimization) כדי
          לבחור עבורך את שילוב הנכסים שמקסים תשואה צפויה ברמת הסיכון שתבחר.
        </p>
        {universe && universe.length > 0 && (
          <details className="mt-3 text-sm text-gray-500">
            <summary className="cursor-pointer hover:text-gray-700">
              למה {universe.length} נכסים ולא 200? (לחץ להסבר)
            </summary>
            <div className="mt-2 leading-relaxed pr-4 border-r-2 border-gray-200">
              היקום שלנו כולל {universe.length} ETFs מובחרים שמכסים 5 מחלקות
              נכסים (מניות, אג"ח, סחורות, נדל"ן, מזומן), 11 סקטורים בארה"ב,
              ו-6 שווקים בינלאומיים. <br />
              <br />
              למה לא יותר? Markowitz אומד μ (תשואה צפויה) ו-Σ (מטריצת
              קוואריאנס) מ-~2,500 ימי מסחר היסטוריים. כל נכס נוסף = יותר
              פרמטרים, אבל אותה כמות נתונים → אומדים פחות מדויקים →
              אופטימיזציה פחות יציבה ("curse of dimensionality" קלאסי).
              30-50 נכסים מאיכות גבוהה זה ה-sweet spot ב-Markowitz סטנדרטי.
              <br />
              <br />
              רוצה להוסיף משהו ספציפי (למשל TSLA, BTC-USD)? פתח את
              "<span className="font-semibold">⚙ מתקדם</span>" בתחתית
              הטופס והוסף ticker מותאם — המערכת תמשוך אותו מ-yfinance
              אוטומטית.
            </div>
          </details>
        )}
      </div>

      <UniverseStatus universe={universe} error={universeError} />

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* === Section 1: Amount + Horizon === */}
        <Section
          number={1}
          title="כמה אתה משקיע ולכמה זמן?"
          subtitle="הסכום הראשוני והאופק קובעים את המסלול שתראה ב-Monte Carlo."
        >
          <div className="grid md:grid-cols-2 gap-4">
            <Field label="סכום השקעה" hint="בין $100 ל-$10M">
              <div className="relative">
                <input
                  type="number"
                  min={100}
                  max={10_000_000}
                  step={100}
                  value={amount}
                  onChange={(e) => setAmount(Number(e.target.value))}
                  className="w-full border rounded px-3 py-2 pr-7 text-lg"
                  required
                />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
              </div>
            </Field>
            <Field label="אופק זמן" hint="בין שנה ל-30. המלצה: 5+">
              <div className="relative">
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={horizon}
                  onChange={(e) => setHorizon(Number(e.target.value))}
                  className="w-full border rounded px-3 py-2 pr-12 text-lg"
                  required
                />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">שנים</span>
              </div>
            </Field>
          </div>
        </Section>

        {/* === Section 2: Risk === */}
        <Section
          number={2}
          title="כמה סיכון אתה מוכן לקחת?"
          subtitle="רמת הסיכון נמדדת כתנודתיות שנתית. ככל שהיא גבוהה יותר — התשואה הצפויה גבוהה יותר, אבל גם הסיכוי להפסדים זמניים."
        >
          <RiskSlider value={risk} onChange={setRisk} />
          <div className="mt-4 p-3 bg-blue-50 border-r-4 border-blue-400 rounded">
            <div className="text-sm text-gray-800 leading-relaxed">
              {RISK_DESCRIPTIONS[risk]}
            </div>
          </div>
        </Section>

        {/* === Section 3: Scope + Country === */}
        <Section
          number={3}
          title="באילו נכסים ואיפה אתה?"
          subtitle="זה משפיע על מה ייכלל בפורטפוליו ועל הערות מיסוי/גישה רלוונטיות."
        >
          <div className="space-y-5">
            <Field label="סוג ההשקעה">
              <div className="space-y-2">
                <RadioOption
                  checked={scope === "all"}
                  onChange={() => setScope("all")}
                  label="תיק מגוון"
                  description="מניות + אג״ח + סחורות + נדל״ן + מזומן (20 נכסים)"
                />
                <RadioOption
                  checked={scope === "equity_only"}
                  onChange={() => setScope("equity_only")}
                  label="רק מניות"
                  description={`רק ETFs של מניות (${equityCountInUniverse} נכסים)`}
                />
              </div>
            </Field>

            <Field label="ארץ מגורים" hint="כדי לתת לך הערות מיסוי/גישה">
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value as Country)}
                className="w-full border rounded px-3 py-2 text-lg bg-white"
              >
                {COUNTRY_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </Field>

            <div className="p-3 bg-amber-50 border-r-4 border-amber-400 rounded">
              <div className="text-sm text-amber-900 leading-relaxed">
                <span className="font-semibold">ℹ הערה: </span>
                {COUNTRY_NOTES[country]}
              </div>
            </div>
          </div>
        </Section>

        {error && (
          <div className="bg-red-50 border-r-4 border-red-500 p-4 rounded">
            <div className="text-red-700 font-medium leading-relaxed">{error}</div>
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !universeReady}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-4 rounded-lg text-lg font-semibold shadow-md transition"
        >
          {submitting
            ? "מחשב את הפורטפוליו האופטימלי..."
            : !universeReady
              ? "טוען נתונים..."
              : `בנה את הפורטפוליו שלי (${effectiveTickers.length} נכסים) ←`}
        </button>

        {/* Advanced — at the bottom, intentionally less visible */}
        <div className="pt-6 border-t">
          {!showAdvanced ? (
            <button
              type="button"
              onClick={() => setShowAdvanced(true)}
              className="text-sm text-gray-500 hover:text-blue-600"
            >
              ⚙ מתקדם: התאם את רשימת הנכסים שהמערכת בוחרת מתוכם
            </button>
          ) : (
            <Section
              number={4}
              title="התאמה אישית של יקום הנכסים (מתקדם)"
              subtitle="הסר סימון כדי להוציא נכס, או הוסף ticker מותאם בתחתית."
            >
              <div className="flex justify-between items-center mb-3 text-sm text-gray-600">
                <span>
                  {tickers.length} נכסים פעילים
                  {excludedCount > 0 && <span className="text-gray-500"> · {excludedCount} הוסרו</span>}
                  {customCount > 0 && <span className="text-blue-600"> · {customCount} מותאמים</span>}
                </span>
                <button
                  type="button"
                  onClick={() => setShowAdvanced(false)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  סגור ▴
                </button>
              </div>
              <UniverseSelector
                universe={universe ?? []}
                selected={tickers}
                onChange={setTickers}
              />
            </Section>
          )}
        </div>
      </form>

      {result && (
        <div id="results" className="mt-12">
          <ResultsPanel portfolio={result} />
        </div>
      )}
    </Layout>
  );
}

// ─── Inline UI building blocks ──────────────────────────────────────────

function UniverseStatus({
  universe,
  error,
}: {
  universe: Asset[] | null;
  error: string | null;
}) {
  if (error) {
    return (
      <div className="mb-6 bg-red-50 border-r-4 border-red-500 p-4 rounded">
        <div className="text-red-700 font-medium">{error}</div>
        <div className="text-sm text-red-600 mt-1">
          ודא שה-backend פעיל (<code>make up</code>) ושההגירות רצו (<code>make migrate</code>).
        </div>
      </div>
    );
  }
  if (universe === null) {
    return (
      <div className="mb-6 bg-gray-50 border-r-4 border-gray-300 p-4 rounded text-gray-700">
        טוען רשימת נכסים מהשרת...
      </div>
    );
  }
  if (universe.length === 0) {
    return (
      <div className="mb-6 bg-yellow-50 border-r-4 border-yellow-500 p-4 rounded">
        <div className="text-yellow-800 font-medium">המערכת ריקה מנכסים.</div>
        <div className="text-sm text-yellow-700 mt-1 leading-relaxed">
          הזרעה הראשונית עדיין לא רצה. הרץ:{" "}
          <code className="bg-yellow-100 px-1 rounded">make seed</code>{" "}
          ואחרי שזה מסתיים — רענן.
        </div>
      </div>
    );
  }
  return null;
}

function Section({
  number,
  title,
  subtitle,
  children,
}: {
  number: number;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="bg-blue-100 text-blue-700 rounded-full w-8 h-8 flex items-center justify-center font-bold flex-shrink-0">
          {number}
        </div>
        <div>
          <h2 className="text-xl font-semibold">{title}</h2>
          <p className="text-sm text-gray-600 mt-0.5 leading-relaxed">{subtitle}</p>
        </div>
      </div>
      <div className="mr-11">{children}</div>
    </section>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      {children}
      {hint && <div className="text-xs text-gray-500 mt-1">{hint}</div>}
    </div>
  );
}

function RadioOption({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
  description?: string;
}) {
  return (
    <label
      className={`block border-2 rounded-lg p-3 cursor-pointer transition ${
        checked ? "border-blue-600 bg-blue-50" : "border-gray-200 hover:border-gray-300"
      }`}
    >
      <div className="flex items-start gap-2">
        <input
          type="radio"
          checked={checked}
          onChange={onChange}
          className="mt-1"
        />
        <div>
          <div className="font-medium">{label}</div>
          {description && (
            <div className="text-sm text-gray-600 mt-0.5">{description}</div>
          )}
        </div>
      </div>
    </label>
  );
}
