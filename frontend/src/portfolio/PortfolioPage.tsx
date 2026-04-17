import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import api, { deletePortfolio, archivePortfolio } from "../api/client";
import Spinner from "../components/Spinner";
import ConfirmDeleteModal from "../components/ConfirmDeleteModal";
import DisclaimerBanner from "./DisclaimerBanner";
import AllocationChart from "./AllocationChart";
import HoldingsTable from "./HoldingsTable";
import HeroScenarioCard from "./HeroScenarioCard";
import RiskGauge from "./RiskGauge";
import DiversificationCard from "./DiversificationCard";
import ScenarioGrid from "./ScenarioGrid";

interface PortfolioData {
  id: string;
  status: string;
  risk_score: number;
  expected_return_low: number;
  expected_return_high: number;
  portfolio_return: number;
  total_value: number;
  holdings: Array<{
    ticker: string;
    company_name: string;
    sector: string;
    allocation_pct: number;
    expected_return: number;
  }>;
  simulation: {
    percentile_10: number;
    percentile_50: number;
    percentile_90: number;
    return_low: number;
    return_high: number;
    initial_value: number;
    horizon_years: number;
    n_simulations: number;
  };
}

export default function PortfolioPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    api.get(`/portfolios/${id}`).then((resp) => {
      setPortfolio(resp.data);
      setLoading(false);
    });
  }, [id]);

  if (loading || !portfolio) return <Spinner />;

  const sortedHoldings = [...portfolio.holdings].sort((a, b) => b.allocation_pct - a.allocation_pct);

  const handleArchive = async () => {
    if (!id) return;
    await archivePortfolio(id);
    navigate("/dashboard");
  };

  const handleDelete = async () => {
    if (!id) return;
    await deletePortfolio(id);
    navigate("/dashboard");
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <Link to="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
          ← Back to Dashboard
        </Link>
        <div className="flex gap-2">
          <button
            onClick={handleArchive}
            className="px-3 py-1.5 text-sm rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700"
          >
            Archive
          </button>
          <button
            onClick={() => setConfirmDelete(true)}
            className="px-3 py-1.5 text-sm rounded-lg bg-red-50 hover:bg-red-100 text-red-700"
          >
            Delete
          </button>
        </div>
      </div>

      <DisclaimerBanner />

      <HeroScenarioCard
        initialValue={portfolio.simulation.initial_value}
        horizonYears={portfolio.simulation.horizon_years}
        percentile10={portfolio.simulation.percentile_10}
        percentile50={portfolio.simulation.percentile_50}
        percentile90={portfolio.simulation.percentile_90}
        nSimulations={portfolio.simulation.n_simulations}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <RiskGauge riskScore={portfolio.risk_score} />
        <DiversificationCard holdings={sortedHoldings} />
      </div>

      <AllocationChart holdings={sortedHoldings} />

      <HoldingsTable holdings={sortedHoldings} />

      <ScenarioGrid
        initialValue={portfolio.simulation.initial_value}
        percentile10={portfolio.simulation.percentile_10}
        percentile50={portfolio.simulation.percentile_50}
        percentile90={portfolio.simulation.percentile_90}
        horizonYears={portfolio.simulation.horizon_years}
      />

      <div className="bg-blue-50 border border-blue-100 p-6 rounded-xl text-center">
        <p className="text-gray-700 mb-3">
          📚 Want to know how we calculated this?
        </p>
        <Link
          to="/methodology"
          className="inline-block px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
        >
          Read the full methodology →
        </Link>
      </div>

      <ConfirmDeleteModal
        open={confirmDelete}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={handleDelete}
      />
    </div>
  );
}
