import InfoTooltip from "../components/InfoTooltip";

interface Props {
  initialValue: number;
  percentile10: number;
  percentile50: number;
  percentile90: number;
  horizonYears: number;
}

function formatMoney(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

export default function ScenarioGrid({
  initialValue, percentile10, percentile50, percentile90, horizonYears,
}: Props) {
  if (horizonYears <= 0) return null;

  const scenarios = [
    {
      label: "Bad years",
      likelihood: "10% chance",
      value: percentile10,
      icon: "📉",
      bg: "bg-red-50",
      border: "border-red-200",
      text: "text-red-700",
      valueText: "text-red-900",
    },
    {
      label: "Typical scenario",
      likelihood: "most likely",
      value: percentile50,
      icon: "📊",
      bg: "bg-blue-50",
      border: "border-blue-200",
      text: "text-blue-700",
      valueText: "text-blue-900",
    },
    {
      label: "Good years",
      likelihood: "10% chance",
      value: percentile90,
      icon: "📈",
      bg: "bg-green-50",
      border: "border-green-200",
      text: "text-green-700",
      valueText: "text-green-900",
    },
  ];

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <div className="flex items-center mb-4">
        <h2 className="text-lg font-semibold">Future Scenarios</h2>
        <InfoTooltip
          text="We split the simulated outcomes into three buckets: the worst 10%, the middle (most likely), and the best 10%. Real outcomes will almost certainly fall somewhere in this range."
          learnMoreAnchor="simulation"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scenarios.map((s) => (
          <div key={s.label} className={`${s.bg} ${s.border} border rounded-xl p-4`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xl">{s.icon}</span>
              <span className={`text-xs ${s.text}`}>{s.likelihood}</span>
            </div>
            <p className={`text-sm font-medium ${s.text}`}>{s.label}</p>
            <p className={`text-2xl font-bold ${s.valueText} mt-1`}>{formatMoney(s.value)}</p>
            <p className="text-xs text-gray-500 mt-1">
              from {formatMoney(initialValue)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
