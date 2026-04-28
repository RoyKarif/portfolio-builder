// Main page: friendly form on top, results below after submission.
//
// Design principles:
//   - Default: user gives only 3 inputs (amount, horizon, risk). Asset
//     selection is hidden behind a "customize" expander, because most
//     users don't know what tickers to pick.
//   - Each section has a header with a question and a one-line subtitle
//     explaining what the input means.
//   - The risk slider shows a plain-language description of the chosen level.
//   - The submit button is large and primary-colored.

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Layout } from "../components/Layout";
import { RiskSlider } from "../components/RiskSlider";
import { UniverseSelector } from "../components/UniverseSelector";
import { ResultsPanel } from "../components/ResultsPanel";
import { api } from "../api";
import type { Asset, PortfolioResponse } from "../types/api";

// What each risk level *feels* like in plain language. Helps the user
// understand what they're choosing.
const RISK_DESCRIPTIONS: Record<number, string> = {
  1: "תיק שמרני מאוד: רוב הכסף באג\"ח ומזומן. תנודות קטנות, תשואה צנועה. מתאים למי שמתעב הפסדים אפילו זמניים.",
  2: "תיק שמרני: בעיקר אג\"ח עם אחוז קטן של מניות. תנודתיות נמוכה.",
  3: "תיק מאוזן: שילוב קלאסי של מניות ואג\"ח. מתאים לרוב המשקיעים לטווח בינוני-ארוך.",
  4: "תיק אגרסיבי מתון: רוב הכסף במניות, עם כרית בטחון של אג\"ח. תנודות חזקות יותר.",
  5: "תיק אגרסיבי: כמעט הכל במניות. תשואה צפויה גבוהה, אבל גם הפסדים זמניים יכולים להיות משמעותיים.",
};

export function BuildPage() {
  const [universe, setUniverse] = useState<Asset[]>([]);
  const [amount, setAmount] = useState(10000);
  const [risk, setRisk] = useState(3);
  const [horizon, setHorizon] = useState(10);
  const [tickers, setTickers] = useState<string[]>([]);
  const [showCustomize, setShowCustomize] = useState(false);
  const [result, setResult] = useState<PortfolioResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // On mount: load the curated universe and pre-select all of it.
  useEffect(() => {
    api.universe.getCurated().then((u) => {
      setUniverse(u);
      setTickers(u.map((a) => a.ticker));
    });
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (tickers.length < 2) {
      setError("יש לבחור לפחות 2 נכסים");
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
      // Smooth scroll to results.
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

  // Customs = tickers the user added that aren't in the curated universe.
  const customCount = tickers.filter(
    (t) => !universe.some((a) => a.ticker === t),
  ).length;
  const excludedCount = universe.filter(
    (a) => !tickers.includes(a.ticker),
  ).length;

  return (
    <Layout>
      {/* Title & subtitle */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">בנה פורטפוליו השקעות</h1>
        <p className="text-gray-600 mt-2 leading-relaxed">
          הכלי משתמש במודל המתמטי של מרקוביץ' (Mean-Variance Optimization) כדי
          לבחור עבורך את שילוב הנכסים שמקסים תשואה צפויה ברמת הסיכון שתבחר.
          ענה על שלוש שאלות, ולחץ "בנה".
        </p>
      </div>

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
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                  $
                </span>
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
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                  שנים
                </span>
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

        {/* === Section 3 (collapsible): Customize universe === */}
        <Section
          number={3}
          title="יקום הנכסים"
          subtitle="הכלי בוחר אוטומטית מתוך 20 ETFs נבחרים. תוכל להסיר או להוסיף לפי טעמך."
        >
          {!showCustomize ? (
            <div className="flex items-center justify-between bg-gray-50 rounded p-4">
              <div>
                <div className="font-medium">
                  משתמשים ב-{tickers.length} נכסים
                  {excludedCount > 0 && (
                    <span className="text-gray-500"> ({excludedCount} הוסרו)</span>
                  )}
                  {customCount > 0 && (
                    <span className="text-blue-600"> ({customCount} מותאמים)</span>
                  )}
                </div>
                <div className="text-sm text-gray-500 mt-1">
                  ברירת המחדל: כל ה-ETFs הנבחרים. אפשר לערוך.
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowCustomize(true)}
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                התאם אישית ←
              </button>
            </div>
          ) : (
            <div>
              <div className="flex justify-between items-center mb-3">
                <span className="text-sm text-gray-600">
                  בטל סימון כדי להסיר נכס. הוסף ticker מותאם בתחתית.
                </span>
                <button
                  type="button"
                  onClick={() => setShowCustomize(false)}
                  className="text-gray-500 hover:text-gray-700 text-sm"
                >
                  סגור ▴
                </button>
              </div>
              <UniverseSelector
                universe={universe}
                selected={tickers}
                onChange={setTickers}
              />
            </div>
          )}
        </Section>

        {error && (
          <div className="bg-red-50 border-r-4 border-red-500 p-4 rounded">
            <div className="text-red-700 font-medium">{error}</div>
          </div>
        )}

        {/* === Submit === */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-4 rounded-lg text-lg font-semibold shadow-md transition"
        >
          {submitting ? "מחשב את הפורטפוליו האופטימלי..." : "בנה את הפורטפוליו שלי ←"}
        </button>
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
