import { Link } from "react-router-dom";
import { MouseEvent } from "react";

interface Props {
  id: string;
  status: string;
  riskScore: number;
  expectedReturnLow: number;
  expectedReturnHigh: number;
  totalValue: number;
  createdAt: string;
  onDelete: (id: string) => void;
}

export default function PortfolioCard({
  id, status, riskScore, expectedReturnLow, expectedReturnHigh, totalValue, createdAt, onDelete,
}: Props) {
  const handleDeleteClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete(id);
  };

  return (
    <Link
      to={`/portfolio/${id}`}
      className="group relative block bg-white p-6 rounded-lg shadow hover:shadow-md transition-shadow"
    >
      <button
        type="button"
        onClick={handleDeleteClick}
        className="absolute top-3 right-3 w-8 h-8 rounded-full bg-gray-100 text-gray-500 hover:bg-red-100 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
        aria-label="Delete portfolio"
        title="Delete portfolio"
      >
        🗑️
      </button>
      <div className="flex justify-between items-start mb-3 pr-8">
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
