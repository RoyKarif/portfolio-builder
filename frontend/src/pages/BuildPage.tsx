// Main page: friendly form on top, results below after submission.
//
// Design principle: the user gives 2 inputs (amount+horizon and risk).
// Asset selection is COMPLETELY hidden by default — most users don't
// know what tickers are. Only a small "advanced" link reveals it.

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Layout } from "../components/Layout";
import { RiskSlider } from "../components/RiskSlider";
import { UniverseSelector } from "../components/UniverseSelector";
import { ResultsPanel } from "../components/ResultsPanel";
import { api } from "../api";
import type { Asset, PortfolioResponse } from "../types/api";

// Plain-language description of what each risk level means.
const RISK_DESCRIPTIONS: Record<number, string> = {
  1: "תיק שמרני מאוד: רוב הכסף באג\"ח ומזומן. תנודות קטנות, תשואה צנועה. מתאים למי שמתעב הפסדים אפילו זמניים.",
  2: "תיק שמרני: בעיקר אג\"ח עם אחוז קטן של מניות. תנודתיות נמוכה.",
  3: "תיק מאוזן: שילוב קלאסי של מניות ואג\"ח. מתאים לרוב המשקיעים לטווח בינוני-ארוך.",
  4: "תיק אגרסיבי מתון: רוב הכסף במניות, עם כרית בטחון של אג\"ח. תנודות חזקות יותר.",
  5: "תיק אגרסיבי: כמעט הכל במניות. תשואה צפויה גבוהה, אבל גם הפסדים זמניים יכולים להיות משמעותיים.",
};

export function BuildPage() {
  // universe = the curated tickers from the backend. null = still loading,
  // [] = loaded but empty (seed wasn't run), [...] = ready.
  const [universe, setUniverse] = useState<Asset[] | null>(null);
  const [universeError, setUniverseError] = useState<string | null>(null);

  const [amount, setAmount] = useState(10000);
  const [risk, setRisk] = useState(3);
  const [horizon, setHorizon] = useState(10);

  // Tickers actually used for the build. By default = entire universe.
  // Only changed if the user opens the advanced customizer.
  const [tickers, setTickers] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [result, setResult] = useState<PortfolioResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load curated universe on mount.
  useEffect(() => {
    api.universe.getCurated()
      .then((u) => {
        setUniverse(u);
        setTickers(u.map((a) => a.ticker));  // pre-select everything
      })
      .catch(() => {
        setUniverseError("לא הצלחתי לטעון את רשימת הנכסים מהשרת.");
      });
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Guard: universe not yet loaded.
    if (universe === null) {
      setError("הנתונים עדיין נטענים. רגע אחד...");
      return;
    }

    // Guard: universe is empty — seed hasn't run.
    if (universe.length === 0) {
      setError(
        "המערכת ריקה מנכסים. כנראה שהזרעה הראשונית עדיין לא רצה. " +
        "הרץ בטרמינל את הפקודה: make seed (זה לוקח ~5 דקות)."
      );
      return;
    }

    // Guard: user opened advanced and deselected too many.
    if (tickers.length < 2) {
      setError(
        "במצב מתקדם: הסרת יותר מדי נכסים. השאר לפחות 2 כדי שהמערכת תוכל לחשב פיזור."
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
        tickers,
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
      {/* Title & subtitle */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">בנה פורטפוליו השקעות</h1>
        <p className="text-gray-600 mt-2 leading-relaxed">
          הכלי משתמש במודל המתמטי של מרקוביץ' (Mean-Variance Optimization) כדי
          לבחור עבורך את שילוב הנכסים שמקסים תשואה צפויה ברמת הסיכון שתבחר.
          ענה על שתי שאלות, ולחץ "בנה".
        </p>
      </div>

      {/* Universe-loading status banner */}
      <UniverseStatus
        universe={universe}
        error={universeError}
      />

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
            <Field label="אופק זמן" hint="בין שנה ל-30 שנה. המלצה: 5+">
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

        {error && (
          <div className="bg-red-50 border-r-4 border-red-500 p-4 rounded">
            <div className="text-red-700 font-medium leading-relaxed">{error}</div>
          </div>
        )}

        {/* === Submit === */}
        <button
          type="submit"
          disabled={submitting || !universeReady}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-4 rounded-lg text-lg font-semibold shadow-md transition"
        >
          {submitting
            ? "מחשב את הפורטפוליו האופטימלי..."
            : !universeReady
              ? "טוען נתונים..."
              : "בנה את הפורטפוליו שלי ←"}
        </button>

        {/* === Advanced (collapsible) — at the BOTTOM, intentionally less visible === */}
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
              number={3}
              title="התאמה אישית של יקום הנכסים (מתקדם)"
              subtitle="המערכת בוחרת אוטומטית מתוך הרשימה. הסר סימון כדי להוציא נכס, או הוסף ticker מותאם בתחתית."
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
          הזרעה הראשונית של 10 שנות מחירים עדיין לא רצה. הרץ בטרמינל:{" "}
          <code className="bg-yellow-100 px-1 rounded">make seed</code>{" "}
          (לוקח ~5 דקות, מוריד מ-yfinance). אחרי שזה מסתיים — רענן את הדף.
        </div>
      </div>
    );
  }
  // Universe loaded successfully — no banner.
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
