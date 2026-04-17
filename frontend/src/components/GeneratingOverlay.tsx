import { useEffect, useState } from "react";

const STAGES = [
  { label: "Selecting candidate stocks...", at: 0 },
  { label: "Downloading market data...", at: 2 },
  { label: "Training prediction models...", at: 6 },
  { label: "Optimizing portfolio weights...", at: 12 },
  { label: "Running Monte Carlo simulation...", at: 16 },
  { label: "Finalizing your portfolio...", at: 20 },
];

const EXPECTED_SECONDS = 25;

export default function GeneratingOverlay({ sectorCount }: { sectorCount: number }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 0.1), 100);
    return () => clearInterval(id);
  }, []);

  const expected = Math.max(EXPECTED_SECONDS, sectorCount * 4);
  const stage =
    [...STAGES].reverse().find((s) => elapsed >= s.at) ?? STAGES[0];
  const progress = Math.min(95, (elapsed / expected) * 100);

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-2xl p-10 max-w-md w-full mx-4">
        <div className="flex justify-center mb-6">
          <div className="relative">
            <div className="w-20 h-20 rounded-full border-4 border-blue-100"></div>
            <div className="w-20 h-20 rounded-full border-4 border-blue-600 border-t-transparent animate-spin absolute top-0"></div>
          </div>
        </div>

        <h2 className="text-xl font-bold text-center mb-2">
          Building Your Portfolio
        </h2>
        <p className="text-gray-600 text-center text-sm mb-6 min-h-[1.25rem]">
          {stage.label}
        </p>

        <div className="w-full bg-gray-100 rounded-full h-2 mb-3 overflow-hidden">
          <div
            className="bg-blue-600 h-full rounded-full transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          ></div>
        </div>

        <div className="flex justify-between text-xs text-gray-500">
          <span>{elapsed.toFixed(1)}s elapsed</span>
          <span>~{expected}s expected</span>
        </div>

        <p className="text-xs text-gray-400 text-center mt-6">
          Analyzing market data, training ML models, and optimizing allocations.
          This typically takes 10-30 seconds.
        </p>
      </div>
    </div>
  );
}
