import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";
import GeneratingOverlay from "../components/GeneratingOverlay";

const SECTORS = [
  "Technology", "Healthcare", "Energy", "Finance",
  "Consumer", "Real Estate", "Industrial",
];

const HORIZONS = [
  { value: "6m", label: "6 months" },
  { value: "1-3y", label: "1-3 years" },
  { value: "3-5y", label: "3-5 years" },
  { value: "5y+", label: "5+ years" },
];

export default function ProfileForm() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [riskLevel, setRiskLevel] = useState(3);
  const [horizon, setHorizon] = useState("3-5y");
  const [amount, setAmount] = useState("");
  const [targetReturn, setTargetReturn] = useState("");
  const [sectors, setSectors] = useState<string[]>([]);
  const [includeTickers, setIncludeTickers] = useState("");
  const [excludeTickers, setExcludeTickers] = useState("");

  const riskLabels = ["", "Very Conservative", "Conservative", "Balanced", "Aggressive", "Very Aggressive"];

  const toggleSector = (sector: string) => {
    setSectors((prev) =>
      prev.includes(sector) ? prev.filter((s) => s !== sector) : [...prev, sector]
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const profileResp = await api.post("/profiles", {
        risk_level: riskLevel,
        investment_horizon: horizon,
        available_amount: parseFloat(amount),
        target_return: parseFloat(targetReturn),
        preferred_sectors: sectors,
        include_tickers: includeTickers ? includeTickers.split(",").map((t) => t.trim().toUpperCase()) : [],
        exclude_tickers: excludeTickers ? excludeTickers.split(",").map((t) => t.trim().toUpperCase()) : [],
      });

      const portfolioResp = await api.post(`/portfolios/generate/${profileResp.data.id}`);
      navigate(`/portfolio/${portfolioResp.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to generate portfolio");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      {loading && <GeneratingOverlay sectorCount={sectors.length} />}
      <h1 className="text-2xl font-bold mb-6">Build Your Portfolio</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {error && <p className="text-red-500 bg-red-50 p-3 rounded">{error}</p>}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Investment Amount ($)
          </label>
          <input
            type="number" min="1000" step="100" value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full p-3 border rounded" required
            placeholder="e.g. 50000"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Risk Level: <span className="font-bold text-blue-600">{riskLabels[riskLevel]}</span>
          </label>
          <input
            type="range" min="1" max="5" value={riskLevel}
            onChange={(e) => setRiskLevel(parseInt(e.target.value))}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span>Conservative</span><span>Aggressive</span>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Investment Horizon</label>
          <div className="grid grid-cols-4 gap-2">
            {HORIZONS.map((h) => (
              <button
                key={h.value} type="button"
                onClick={() => setHorizon(h.value)}
                className={`p-2 rounded border text-sm ${
                  horizon === h.value ? "bg-blue-600 text-white border-blue-600" : "bg-white hover:bg-gray-50"
                }`}
              >
                {h.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Target Annual Return (%)
          </label>
          <input
            type="number" min="1" max="50" step="0.5" value={targetReturn}
            onChange={(e) => setTargetReturn(e.target.value)}
            className="w-full p-3 border rounded" required
            placeholder="e.g. 10"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Sectors</label>
          <div className="flex flex-wrap gap-2">
            {SECTORS.map((sector) => (
              <button
                key={sector} type="button"
                onClick={() => toggleSector(sector)}
                className={`px-3 py-1.5 rounded-full text-sm border ${
                  sectors.includes(sector)
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white hover:bg-gray-50"
                }`}
              >
                {sector}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Include Tickers</label>
            <input
              type="text" value={includeTickers}
              onChange={(e) => setIncludeTickers(e.target.value)}
              className="w-full p-3 border rounded" placeholder="AAPL, MSFT"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Exclude Tickers</label>
            <input
              type="text" value={excludeTickers}
              onChange={(e) => setExcludeTickers(e.target.value)}
              className="w-full p-3 border rounded" placeholder="META, TSLA"
            />
          </div>
        </div>

        <button
          type="submit" disabled={loading || sectors.length === 0}
          className="w-full bg-blue-600 text-white p-3 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Generating Portfolio..." : "Generate Portfolio"}
        </button>
      </form>
    </div>
  );
}
