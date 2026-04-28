// Main page: form on top, results below after submission.
import { useEffect, useState, type FormEvent } from "react";
import { Layout } from "../components/Layout";
import { RiskSlider } from "../components/RiskSlider";
import { UniverseSelector } from "../components/UniverseSelector";
import { ResultsPanel } from "../components/ResultsPanel";
import { api } from "../api";
import type { Asset, PortfolioResponse } from "../types/api";

export function BuildPage() {
  const [universe, setUniverse] = useState<Asset[]>([]);
  const [amount, setAmount] = useState(10000);
  const [risk, setRisk] = useState(3);
  const [horizon, setHorizon] = useState(10);
  const [tickers, setTickers] = useState<string[]>([]);
  const [result, setResult] = useState<PortfolioResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load curated universe on mount; pre-select all of it.
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
      setError("בחר לפחות 2 נכסים");
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
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        ?? "שגיאה בבניית הפורטפוליו";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <h1 className="text-2xl font-bold mb-6">בנה פורטפוליו</h1>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded shadow p-6 space-y-4 mb-8"
      >
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">סכום השקעה ($)</label>
            <input
              type="number"
              min={100}
              max={10_000_000}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">אופק זמן (שנים)</label>
            <input
              type="number"
              min={1}
              max={30}
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="w-full border rounded px-3 py-2"
            />
          </div>
        </div>

        <RiskSlider value={risk} onChange={setRisk} />

        <UniverseSelector
          universe={universe}
          selected={tickers}
          onChange={setTickers}
        />

        {error && <div className="text-red-600 text-sm">{error}</div>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-blue-600 text-white py-3 rounded font-semibold hover:bg-blue-700 disabled:bg-gray-400"
        >
          {submitting ? "מחשב..." : "בנה פורטפוליו"}
        </button>
      </form>

      {result && <ResultsPanel portfolio={result} />}
    </Layout>
  );
}
