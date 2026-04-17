import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { deletePortfolio } from "../api/client";
import PortfolioCard from "./PortfolioCard";
import Spinner from "../components/Spinner";
import ConfirmDeleteModal from "../components/ConfirmDeleteModal";

interface PortfolioItem {
  id: string;
  status: string;
  risk_score: number;
  expected_return_low: number;
  expected_return_high: number;
  total_value: number;
  created_at: string;
}

export default function DashboardPage() {
  const [portfolios, setPortfolios] = useState<PortfolioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    api.get("/portfolios").then((resp) => {
      setPortfolios(resp.data);
      setLoading(false);
    });
  }, []);

  const handleDeleteConfirm = async () => {
    if (!deletingId) return;
    const id = deletingId;
    await deletePortfolio(id);
    setPortfolios((prev) => prev.filter((p) => p.id !== id));
    setDeletingId(null);
  };

  if (loading) return <Spinner />;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">My Portfolios</h1>
        <Link to="/profile/new" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          + New Portfolio
        </Link>
      </div>

      {portfolios.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg mb-4">No portfolios yet</p>
          <Link to="/profile/new" className="text-blue-600 hover:underline">
            Create your first portfolio
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {portfolios.map((p) => (
            <PortfolioCard
              key={p.id}
              id={p.id}
              status={p.status}
              riskScore={p.risk_score}
              expectedReturnLow={p.expected_return_low}
              expectedReturnHigh={p.expected_return_high}
              totalValue={p.total_value}
              createdAt={p.created_at}
              onDelete={setDeletingId}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteModal
        open={!!deletingId}
        onCancel={() => setDeletingId(null)}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
