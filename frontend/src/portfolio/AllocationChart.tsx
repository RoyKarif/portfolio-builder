import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface Holding {
  ticker: string;
  company_name: string;
  allocation_pct: number;
}

const COLORS = ["#2563eb", "#7c3aed", "#059669", "#d97706", "#dc2626", "#0891b2", "#4f46e5", "#be123c"];

export default function AllocationChart({ holdings }: { holdings: Holding[] }) {
  const sorted = [...holdings].sort((a, b) => b.allocation_pct - a.allocation_pct);
  const data = sorted.map((h) => ({
    name: `${h.ticker} (${h.allocation_pct.toFixed(1)}%)`,
    value: h.allocation_pct,
  }));

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-4">What You Own</h2>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
