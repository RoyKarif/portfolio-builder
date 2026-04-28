// Aggregates all six visualization components into one block.
import type { PortfolioResponse } from "../types/api";
import { WeightsTable } from "./WeightsTable";
import { StatsPanel } from "./StatsPanel";
import { EfficientFrontierChart } from "./EfficientFrontierChart";
import { FanChart } from "./FanChart";
import { FinalValueHistogram } from "./FinalValueHistogram";

export function ResultsPanel({ portfolio }: { portfolio: PortfolioResponse }) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">{portfolio.name}</h2>

      <StatsPanel
        expectedReturn={Number(portfolio.expected_return)}
        expectedVolatility={Number(portfolio.expected_volatility)}
        sharpeRatio={Number(portfolio.sharpe_ratio)}
      />

      <div className="grid md:grid-cols-2 gap-4">
        <WeightsTable
          weights={portfolio.weights}
          amount={Number(portfolio.amount)}
        />
        <EfficientFrontierChart
          expectedReturn={Number(portfolio.expected_return)}
          expectedVolatility={Number(portfolio.expected_volatility)}
        />
      </div>

      <FanChart timeline={portfolio.mc_summary.timeline} />

      {portfolio.histogram && (
        <FinalValueHistogram
          histogram={portfolio.histogram}
          initialValue={Number(portfolio.amount)}
          var5={portfolio.mc_summary.var_5}
        />
      )}
    </div>
  );
}
