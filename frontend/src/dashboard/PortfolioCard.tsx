import { Link } from "react-router-dom";

interface Props {
  id: string;
  status: string;
  riskScore: number;
  expectedReturnLow: number;
  expectedReturnHigh: number;
  totalValue: number;
  createdAt: string;
}

export default function PortfolioCard({ id, status, riskScore, expectedReturnLow, expectedReturnHigh, totalValue, createdAt }: Props) {
  return (
    <Link to={`/portfolio/${id}`} className="block bg-white p-6 rounded-lg shadow hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <span className="text-sm text-gray-400">{new Date(createdAt).toLocaleDateString()}</span>
        <span className={`text-xs px-2 py-1 rounded-full ${
          status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
        }`}>
          {status}
        </span>
      </div>
      <p className="text-2xl font-bold mb-1">${totalValue.toLocaleString()}</p>
      <p className="text-sm text-gray-600 mb-2">
        Expected: {expectedReturnLow}% — {expectedReturnHigh}% annual
      </p>
      <p className="text-sm text-gray-500">Risk score: {riskScore}%</p>
    </Link>
  );
}
