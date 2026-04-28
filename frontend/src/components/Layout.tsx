// Shared page wrapper with header (logo + nav + logout button).
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { ReactNode } from "react";

export function Layout({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold">Portfolio Builder</Link>
          <nav className="space-x-4 space-x-reverse flex items-center">
            <Link to="/" className="text-gray-700 hover:text-blue-600">בנייה</Link>
            <Link to="/portfolios" className="text-gray-700 hover:text-blue-600">הפורטפוליואים שלי</Link>
            <button
              onClick={logout}
              className="text-gray-700 hover:text-red-600"
            >
              התנתקות
            </button>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
