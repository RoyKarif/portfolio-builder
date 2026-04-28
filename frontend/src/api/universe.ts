import { apiClient } from "./client";
import type { Asset } from "../types/api";

export const universeApi = {
  async getCurated(): Promise<Asset[]> {
    const r = await apiClient.get<Asset[]>("/universe");
    return r.data;
  },
};
