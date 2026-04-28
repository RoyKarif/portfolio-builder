// Monte Carlo "fan" chart: 5/25/50/75/95 percentile bands over time.
// Built with recharts ComposedChart so we can stack Areas + a Line.

import {
  ComposedChart,
  XAxis,
  YAxis,
  Area,
  Line,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TimelinePoint } from "../types/api";

export function FanChart({ timeline }: { timeline: TimelinePoint[] }) {
  // Recharts doesn't natively support "p25 to p75" bands. We trick it by
  // stacking two Areas: one at p95 (upper-fill) and one at p5 (white,
  // hides the bottom part). Same for the inner band p25/p75.

  return (
    <div className="bg-white rounded shadow p-4">
      <h3 className="font-semibold mb-3">Monte Carlo — תרחישים</h3>
      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={timeline}>
          <XAxis dataKey="year" label={{ value: "שנים", position: "bottom" }} />
          <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
          <Tooltip
            formatter={(v: number) => `$${Math.round(v).toLocaleString()}`}
          />

          {/* Outer band 5–95 */}
          <Area dataKey="p95" stroke="none" fill="#bfdbfe" fillOpacity={0.5} />
          <Area dataKey="p5" stroke="none" fill="#ffffff" fillOpacity={1} />

          {/* Inner band 25–75 */}
          <Area dataKey="p75" stroke="none" fill="#60a5fa" fillOpacity={0.5} />
          <Area dataKey="p25" stroke="none" fill="#ffffff" fillOpacity={1} />

          {/* Median line */}
          <Line
            dataKey="p50"
            stroke="#1e40af"
            strokeWidth={2}
            dot={false}
            type="monotone"
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-2 text-xs text-gray-500 flex space-x-3 space-x-reverse">
        <span>● חציון</span>
        <span>▮ 25%–75%</span>
        <span>▯ 5%–95%</span>
      </div>
    </div>
  );
}
