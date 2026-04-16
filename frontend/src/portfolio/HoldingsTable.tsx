interface Holding {
  ticker: string;
  company_name: string;
  sector: string;
  allocation_pct: number;
  expected_return: number;
}

export default function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-lg font-semibold mb-4">Holdings</h2>
      <table className="w-full text-left">
        <thead>
          <tr className="border-b text-sm text-gray-500">
            <th className="py-2">Ticker</th>
            <th>Company</th>
            <th>Sector</th>
            <th className="text-right">Allocation</th>
            <th className="text-right">Expected Return</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.ticker} className="border-b hover:bg-gray-50">
              <td className="py-3 font-mono font-bold">{h.ticker}</td>
              <td>{h.company_name}</td>
              <td className="text-sm text-gray-600">{h.sector}</td>
              <td className="text-right">{h.allocation_pct}%</td>
              <td className="text-right text-green-600">{h.expected_return}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
