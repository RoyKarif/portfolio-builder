// Lists the user's saved portfolios. Click → detail page.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { api } from "../api";
import type { PortfolioListItem } from "../types/api";

export function PortfoliosListPage() {
  const [items, setItems] = useState<PortfolioListItem[] | null>(null);

  useEffect(() => {
    api.portfolio.list().then(setItems);
  }, []);

  return (
    <Layout>
      <h1 className="text-2xl font-bold mb-6">הפורטפוליואים שלי</h1>

      {items === null && <div>טוען...</div>}
      {items?.length === 0 && (
        <div className="bg-white rounded shadow p-6 text-center text-gray-600">
          עדיין אין פורטפוליואים. <Link to="/" className="text-blue-600">בנה אחד</Link>.
        </div>
      )}

      {items && items.length > 0 && (
        <div className="bg-white rounded shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="text-right px-4 py-3">שם</th>
                <th className="text-right px-4 py-3">תאריך</th>
                <th className="text-right px-4 py-3">סכום</th>
                <th className="text-right px-4 py-3">סיכון</th>
                <th className="text-right px-4 py-3">תשואה צפויה</th>
                <th className="text-right px-4 py-3">תנודתיות</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/portfolios/${p.id}`} className="text-blue-600">
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    {new Date(p.created_at).toLocaleDateString("he-IL")}
                  </td>
                  <td className="px-4 py-3">${Number(p.amount).toLocaleString()}</td>
                  <td className="px-4 py-3">{p.risk_level}/5</td>
                  <td className="px-4 py-3">{(Number(p.expected_return) * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3">{(Number(p.expected_volatility) * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
