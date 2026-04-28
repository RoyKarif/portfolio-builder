// 1..5 risk slider with a label that updates live.
const LABELS: Record<number, string> = {
  1: "שמרני מאוד",
  2: "שמרני",
  3: "מאוזן",
  4: "אגרסיבי",
  5: "אגרסיבי מאוד",
};

const VOLS: Record<number, string> = {
  1: "5%",
  2: "8%",
  3: "12%",
  4: "16%",
  5: "20%",
};

export function RiskSlider({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <label className="text-sm font-medium">רמת סיכון</label>
        <span className="text-sm text-gray-600">
          {LABELS[value]} (תנודתיות יעד {VOLS[value]})
        </span>
      </div>
      <input
        type="range"
        min={1}
        max={5}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>שמרני</span>
        <span>אגרסיבי</span>
      </div>
    </div>
  );
}
