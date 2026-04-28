// View a saved portfolio by id (from URL).
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Layout } from "../components/Layout";
import { ResultsPanel } from "../components/ResultsPanel";
import { api } from "../api";
import type { PortfolioResponse } from "../types/api";

export function PortfolioDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.portfolio.get(Number(id))
      .then(setPortfolio)
      .catch(() => setError("הפורטפוליו לא נמצא"));
  }, [id]);

  return (
    <Layout>
      {error && <div className="text-red-600">{error}</div>}
      {!error && !portfolio && <div>טוען...</div>}
      {portfolio && <ResultsPanel portfolio={portfolio} />}
    </Layout>
  );
}
