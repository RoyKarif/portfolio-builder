import InfoTooltip from "../components/InfoTooltip";

interface Holding {
  ticker: string;
  company_name: string;
  sector: string;
  allocation_pct: number;
  expected_return: number;
}

export default function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const sorted = [...holdings].sort((a, b) => b.allocation_pct - a.allocation_pct);

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-4">Your Stocks</h2>
      <table className="w-full text-left">
        <thead>
          <tr className="border-b text-sm text-gray-500">
            <th className="py-2">Ticker</th>
            <th>Company</th>
            <th>Sector</th>
            <th className="text-right">
              Allocation
              <InfoTooltip text="What percentage of your total investment goes into this stock." />
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((h) => (
            <tr key={h.ticker} className="border-b hover:bg-gray-50">
              <td className="py-3 font-mono font-bold">{h.ticker}</td>
              <td>{h.company_name}</td>
              <td className="text-sm text-gray-600">{h.sector}</td>
              <td className="text-right font-semibold">{h.allocation_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
