// Auth state for the whole app. Stored in React Context so any
// component can read or update it via useAuth().
//
// Token persistence: localStorage. Survives page refresh.
// Trade-off: localStorage is XSS-readable. For a tutorial-grade project
// this is acceptable; production-grade would use httpOnly cookies.

import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import { api } from "../api";
import { TOKEN_KEY } from "../api/client";

interface AuthContextValue {
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY),
  );

  // Persist any change to the token in localStorage.
  useEffect(() => {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  }, [token]);

  const login = async (email: string, password: string) => {
    const r = await api.auth.login(email, password);
    setToken(r.access_token);
  };

  const register = async (email: string, password: string) => {
    const r = await api.auth.register(email, password);
    setToken(r.access_token);
  };

  const logout = () => setToken(null);

  return (
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated: token !== null,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
