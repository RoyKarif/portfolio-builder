import { apiClient } from "./client";
import type {
  PortfolioBuildRequest,
  PortfolioResponse,
  PortfolioListItem,
} from "../types/api";

export const portfolioApi = {
  async build(req: PortfolioBuildRequest): Promise<PortfolioResponse> {
    const r = await apiClient.post<PortfolioResponse>("/portfolios/build", req);
    return r.data;
  },

  async list(): Promise<PortfolioListItem[]> {
    const r = await apiClient.get<PortfolioListItem[]>("/portfolios");
    return r.data;
  },

  async get(id: number): Promise<PortfolioResponse> {
    const r = await apiClient.get<PortfolioResponse>(`/portfolios/${id}`);
    return r.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/portfolios/${id}`);
  },
};
