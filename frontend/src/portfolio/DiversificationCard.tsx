import InfoTooltip from "../components/InfoTooltip";

interface Holding {
  sector: string;
}

interface Props {
  holdings: Holding[];
}

export default function DiversificationCard({ holdings }: Props) {
  const sectorCount = new Set(holdings.map((h) => h.sector)).size;
  const stockCount = holdings.length;
  const good = sectorCount >= 3 && stockCount >= 5;

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-500">
          Diversification
          <InfoTooltip
            text="Spreading your money across many stocks and sectors reduces the impact of any single one performing badly."
            learnMoreAnchor="optimization"
          />
        </h3>
        <span className={`text-xs px-2 py-0.5 rounded-full ${good ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
          {good ? "Well diversified" : "Limited"}
        </span>
      </div>
      <p className="text-2xl font-bold mb-1 text-gray-900">{stockCount} stocks</p>
      <p className="text-sm text-gray-600">across {sectorCount} sector{sectorCount === 1 ? "" : "s"}</p>
    </div>
  );
}
