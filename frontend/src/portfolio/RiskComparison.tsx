interface Props {
  riskScore: number;
  expectedReturnLow: number;
  expectedReturnHigh: number;
}

export default function RiskComparison({ riskScore, expectedReturnLow, expectedReturnHigh }: Props) {
  const riskLabel = riskScore < 10 ? "Low" : riskScore < 20 ? "Moderate" : riskScore < 30 ? "High" : "Very High";
  const riskColor = riskScore < 10 ? "text-green-600" : riskScore < 20 ? "text-yellow-600" : riskScore < 30 ? "text-orange-600" : "text-red-600";

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-4">Risk Assessment</h2>
      <div className="flex items-center gap-6">
        <div className="text-center">
          <p className="text-sm text-gray-500">Risk Score</p>
          <p className={`text-3xl font-bold ${riskColor}`}>{riskScore}%</p>
          <p className={`text-sm font-medium ${riskColor}`}>{riskLabel} Volatility</p>
        </div>
        <div className="flex-1">
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className="bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 h-4 rounded-full"
              style={{ width: `${Math.min(riskScore * 2.5, 100)}%` }}
            />
          </div>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-500">Expected Return</p>
          <p className="text-xl font-bold text-blue-600">
            {expectedReturnLow}% — {expectedReturnHigh}%
          </p>
          <p className="text-sm text-gray-400">annual</p>
        </div>
      </div>
    </div>
  );
}
