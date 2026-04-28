// Histogram of final portfolio values + a vertical VaR-5% marker.

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { HistogramData } from "../types/api";

interface Props {
  histogram: HistogramData;
  initialValue: number;
  var5: number;  // negative number = loss
}

export function FinalValueHistogram({ histogram, initialValue, var5 }: Props) {
  // Convert (counts, edges) into recharts data.
  const bins = histogram.counts.map((count, i) => ({
    midpoint: (histogram.edges[i] + histogram.edges[i + 1]) / 2,
    count,
  }));

  const var5Threshold = initialValue + var5; // positive number

  return (
    <div className="bg-white rounded shadow p-4">
      <h3 className="font-semibold mb-1">התפלגות תוצאות סופיות</h3>
      <div className="text-sm text-gray-600 mb-3">
        VaR 5%: בתסריט הגרוע ב-5% מהמקרים, התיק שווה לפחות{" "}
        <span className="font-bold">${Math.round(var5Threshold).toLocaleString()}</span>
        {" "}({var5 < 0 ? "הפסד" : "רווח"} של ${Math.round(Math.abs(var5)).toLocaleString()})
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={bins}>
          <XAxis
            dataKey="midpoint"
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          />
          <YAxis />
          <Tooltip
            formatter={(v: number) => `${v} מסלולים`}
            labelFormatter={(v: number) => `~$${Math.round(v).toLocaleString()}`}
          />
          <ReferenceLine
            x={var5Threshold}
            stroke="red"
            strokeDasharray="3 3"
            label={{ value: "VaR 5%", position: "top", fill: "red" }}
          />
          <ReferenceLine
            x={initialValue}
            stroke="gray"
            strokeDasharray="3 3"
            label={{ value: "התחלה", position: "top", fill: "gray" }}
          />
          <Bar dataKey="count" fill="#60a5fa" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
