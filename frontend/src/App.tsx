import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import LoginPage from "./auth/LoginPage";
import RegisterPage from "./auth/RegisterPage";
import Layout from "./components/Layout";
import DashboardPage from "./dashboard/DashboardPage";
import ProfileForm from "./profile/ProfileForm";
import PortfolioPage from "./portfolio/PortfolioPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/dashboard" element={
            <ProtectedRoute><Layout><DashboardPage /></Layout></ProtectedRoute>
          } />
          <Route path="/profile/new" element={
            <ProtectedRoute><Layout><ProfileForm /></Layout></ProtectedRoute>
          } />
          <Route path="/portfolio/:id" element={
            <ProtectedRoute><Layout><PortfolioPage /></Layout></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
