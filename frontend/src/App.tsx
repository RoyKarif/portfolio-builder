// Root component. Wires up:
//   1. AuthProvider (token state)
//   2. BrowserRouter (URL ↔ component)
//   3. Routes — public (/login, /register) and protected (/, /portfolios, /portfolios/:id)

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { LoginPage } from "./auth/LoginPage";
import { RegisterPage } from "./auth/RegisterPage";
import { BuildPage } from "./pages/BuildPage";
import { PortfoliosListPage } from "./pages/PortfoliosListPage";
import { PortfolioDetailPage } from "./pages/PortfolioDetailPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<BuildPage />} />
            <Route path="/portfolios" element={<PortfoliosListPage />} />
            <Route path="/portfolios/:id" element={<PortfolioDetailPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
