// Three stat cards: expected return, expected volatility, Sharpe.

interface Props {
  expectedReturn: number;
  expectedVolatility: number;
  sharpeRatio: number;
}

export function StatsPanel({ expectedReturn, expectedVolatility, sharpeRatio }: Props) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <Card label="תשואה צפויה" value={`${(expectedReturn * 100).toFixed(2)}%`} />
      <Card label="תנודתיות צפויה" value={`${(expectedVolatility * 100).toFixed(2)}%`} />
      <Card label="Sharpe Ratio" value={sharpeRatio.toFixed(2)} />
    </div>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded shadow p-4 text-center">
      <div className="text-xs text-gray-500 uppercase">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}
