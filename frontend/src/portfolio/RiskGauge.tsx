import InfoTooltip from "../components/InfoTooltip";

interface Props {
  riskScore: number;
}

function classify(score: number): { label: string; level: number; color: string; bg: string } {
  if (score < 15) return { label: "Low risk", level: 1, color: "text-green-700", bg: "bg-green-500" };
  if (score < 25) return { label: "Medium-low risk", level: 2, color: "text-lime-700", bg: "bg-lime-500" };
  if (score < 35) return { label: "Medium risk", level: 3, color: "text-yellow-700", bg: "bg-yellow-500" };
  if (score < 50) return { label: "High risk", level: 4, color: "text-orange-700", bg: "bg-orange-500" };
  return { label: "Very high risk", level: 5, color: "text-red-700", bg: "bg-red-500" };
}

export default function RiskGauge({ riskScore }: Props) {
  const { label, level, color, bg } = classify(riskScore);

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-500">
          Risk Level
          <InfoTooltip
            text="How much your portfolio's value may swing up or down. Higher risk means bigger potential gains and losses."
            learnMoreAnchor="risk"
          />
        </h3>
        <span className="text-xs text-gray-400">{riskScore.toFixed(1)}% volatility</span>
      </div>
      <p className={`text-2xl font-bold mb-4 ${color}`}>{label}</p>
      <div className="flex gap-1.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <div
            key={n}
            className={`flex-1 h-2 rounded-full ${n <= level ? bg : "bg-gray-200"}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-2">
        <span>Safer</span>
        <span>Riskier</span>
      </div>
    </div>
  );
}
