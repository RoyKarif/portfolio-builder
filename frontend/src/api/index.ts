// Convenience aggregator — components do `import { api } from "@/api"`
// and use `api.auth.login(...)`, `api.portfolio.build(...)`, etc.
import { authApi } from "./auth";
import { universeApi } from "./universe";
import { portfolioApi } from "./portfolio";

export const api = {
  auth: authApi,
  universe: universeApi,
  portfolio: portfolioApi,
};
