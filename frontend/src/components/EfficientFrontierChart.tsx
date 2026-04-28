// A simplified visualization: shows the user's portfolio as a point
// on a (volatility, return) plane.
//
// For a real efficient frontier we'd need to call solve_mvo at several
// volatility levels. Here we show just the "you are here" marker on
// labeled axes — clearer for non-finance users than a dense scatter.

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ReferenceDot,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

interface Props {
  expectedReturn: number;
  expectedVolatility: number;
}

export function EfficientFrontierChart({ expectedReturn, expectedVolatility }: Props) {
  const data = [
    { x: expectedVolatility * 100, y: expectedReturn * 100 },
  ];

  return (
    <div className="bg-white rounded shadow p-4">
      <h3 className="font-semibold mb-3">מיקום בתפיסת סיכון-תשואה</h3>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="x"
            name="תנודתיות"
            unit="%"
            label={{ value: "תנודתיות שנתית %", position: "bottom" }}
            domain={[0, 25]}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="תשואה"
            unit="%"
            label={{ value: "תשואה שנתית %", angle: -90, position: "left" }}
            domain={[0, 20]}
          />
          <Tooltip
            formatter={(v: number) => `${v.toFixed(2)}%`}
          />
          <Scatter data={data} fill="#dc2626" />
          <ReferenceDot
            x={data[0].x}
            y={data[0].y}
            r={8}
            fill="#dc2626"
            stroke="#7f1d1d"
            label={{ value: "אתה כאן", position: "top", fill: "#7f1d1d" }}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
