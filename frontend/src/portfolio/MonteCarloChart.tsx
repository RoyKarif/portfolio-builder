interface SimulationData {
  percentile_10: number;
  percentile_50: number;
  percentile_90: number;
  return_low: number;
  return_high: number;
  initial_value: number;
  horizon_years: number;
}

export default function MonteCarloChart({ simulation }: { simulation: SimulationData }) {
  const formatCurrency = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

  const formatPct = (n: number) => `${(n * 100).toFixed(1)}%`;

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-4">Monte Carlo Simulation</h2>
      <p className="text-sm text-gray-500 mb-4">
        Based on {simulation.horizon_years} year horizon, 10,000 simulated scenarios
      </p>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-4 bg-red-50 rounded">
          <p className="text-sm text-gray-500">Worst Case (10th %ile)</p>
          <p className="text-xl font-bold text-red-600">{formatCurrency(simulation.percentile_10)}</p>
          <p className="text-sm text-red-500">{formatPct(simulation.return_low)} / year</p>
        </div>
        <div className="text-center p-4 bg-blue-50 rounded">
          <p className="text-sm text-gray-500">Median (50th %ile)</p>
          <p className="text-xl font-bold text-blue-600">{formatCurrency(simulation.percentile_50)}</p>
        </div>
        <div className="text-center p-4 bg-green-50 rounded">
          <p className="text-sm text-gray-500">Best Case (90th %ile)</p>
          <p className="text-xl font-bold text-green-600">{formatCurrency(simulation.percentile_90)}</p>
          <p className="text-sm text-green-500">{formatPct(simulation.return_high)} / year</p>
        </div>
      </div>

      <p className="text-sm text-gray-500 text-center">
        With 80% probability, your portfolio value after {simulation.horizon_years} years
        will be between {formatCurrency(simulation.percentile_10)} and {formatCurrency(simulation.percentile_90)}
      </p>
    </div>
  );
}
