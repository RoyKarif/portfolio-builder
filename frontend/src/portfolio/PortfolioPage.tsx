import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api/client";
import Spinner from "../components/Spinner";
import DisclaimerBanner from "./DisclaimerBanner";
import AllocationChart from "./AllocationChart";
import BacktestChart from "./BacktestChart";
import HoldingsTable from "./HoldingsTable";
import MonteCarloChart from "./MonteCarloChart";
import RiskComparison from "./RiskComparison";

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
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/portfolios/${id}`).then((resp) => {
      setPortfolio(resp.data);
      setLoading(false);
    });
  }, [id]);

  if (loading || !portfolio) return <Spinner />;

  return (
    <div className="space-y-6">
      <DisclaimerBanner />

      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Your Portfolio</h1>
        <span className="text-sm text-gray-500">
          Total Investment: ${portfolio.total_value.toLocaleString()}
        </span>
      </div>

      <RiskComparison
        riskScore={portfolio.risk_score}
        expectedReturnLow={portfolio.expected_return_low}
        expectedReturnHigh={portfolio.expected_return_high}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AllocationChart holdings={portfolio.holdings} />
        <MonteCarloChart simulation={portfolio.simulation} />
      </div>

      <BacktestChart data={[]} initialValue={portfolio.total_value} />

      <HoldingsTable holdings={portfolio.holdings} />
    </div>
  );
}
