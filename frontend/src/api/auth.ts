import { apiClient } from "./client";
import type { TokenResponse } from "../types/api";

export const authApi = {
  async register(email: string, password: string): Promise<TokenResponse> {
    const r = await apiClient.post<TokenResponse>("/auth/register", { email, password });
    return r.data;
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const r = await apiClient.post<TokenResponse>("/auth/login", { email, password });
    return r.data;
  },
};
