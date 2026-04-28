// Renders the optimized weights as a sorted table with percent and dollar columns.

interface Props {
  weights: Record<string, number>;
  amount: number;
}

export function WeightsTable({ weights, amount }: Props) {
  // Show only positive weights, sorted descending.
  const rows = Object.entries(weights)
    .filter(([, w]) => w > 0.001)
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="bg-white rounded shadow p-4">
      <h3 className="font-semibold mb-3">משקלות הפורטפוליו</h3>
      <table className="w-full text-sm">
        <thead className="text-gray-500 border-b">
          <tr>
            <th className="text-right py-2">Ticker</th>
            <th className="text-right py-2">משקל</th>
            <th className="text-right py-2">סכום</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([ticker, weight]) => (
            <tr key={ticker} className="border-b last:border-0">
              <td className="py-2 font-mono font-bold">{ticker}</td>
              <td className="py-2">{(weight * 100).toFixed(1)}%</td>
              <td className="py-2">${(weight * amount).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
