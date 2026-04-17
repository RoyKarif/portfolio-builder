import InfoTooltip from "../components/InfoTooltip";

interface Props {
  initialValue: number;
  horizonYears: number;
  percentile10: number;
  percentile50: number;
  percentile90: number;
  nSimulations: number;
}

function formatMoney(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

function formatYears(y: number): string {
  if (y < 1) return `${Math.round(y * 12)} months`;
  if (y === Math.round(y)) return `${y} year${y === 1 ? "" : "s"}`;
  return `${y.toFixed(1)} years`;
}

export default function HeroScenarioCard({
  initialValue, horizonYears, percentile10, percentile50, percentile90, nSimulations,
}: Props) {
  const unavailable = horizonYears <= 0 || nSimulations <= 0;

  if (unavailable) {
    return (
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-8 rounded-2xl shadow border border-blue-100">
        <p className="text-gray-600 text-center">
          Simulation data is not available for this portfolio.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-8 rounded-2xl shadow-lg text-white">
      <p className="text-blue-100 text-sm mb-2">
        If you invest {formatMoney(initialValue)} today
      </p>
      <p className="text-2xl md:text-3xl font-bold mb-4 leading-snug">
        in {formatYears(horizonYears)} you could have between{" "}
        <span className="text-white">{formatMoney(percentile10)}</span> and{" "}
        <span className="text-white">{formatMoney(percentile90)}</span>.
      </p>
      <p className="text-blue-100">
        Most likely around <span className="font-bold text-white">{formatMoney(percentile50)}</span>.
      </p>
      <div className="mt-6 pt-4 border-t border-white/20 flex items-center justify-between text-xs text-blue-100">
        <span>Based on {nSimulations.toLocaleString()} simulated paths</span>
        <InfoTooltip
          text="We run thousands of randomized future scenarios to estimate a range of possible outcomes. This is not a prediction — it's a distribution of what could happen."
          learnMoreAnchor="simulation"
        />
      </div>
    </div>
  );
}
