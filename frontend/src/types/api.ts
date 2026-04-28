// TypeScript types mirror the backend's Pydantic schemas.
// Whenever the backend changes, the corresponding type here updates,
// and TS finds every component that needs to change.

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  email: string;
  created_at: string;
}

export interface Asset {
  ticker: string;
  name: string;
  asset_class: string;
  is_curated: boolean;
}

export interface PortfolioBuildRequest {
  amount: number;
  risk_level: number;
  horizon_years: number;
  tickers: string[];
  name?: string;
}

export interface TimelinePoint {
  year: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface MCSummary {
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  var_5: number;
  timeline: TimelinePoint[];
}

export interface HistogramData {
  counts: number[];
  edges: number[];
}

export interface PortfolioResponse {
  id: number;
  name: string;
  created_at: string;
  amount: number;
  risk_level: number;
  horizon_years: number;
  target_volatility: number;
  weights: Record<string, number>;
  expected_return: number;
  expected_volatility: number;
  sharpe_ratio: number;
  mc_summary: MCSummary;
  mc_seed: number;
  histogram?: HistogramData;
}

export interface PortfolioListItem {
  id: number;
  name: string;
  created_at: string;
  amount: number;
  risk_level: number;
  horizon_years: number;
  expected_return: number;
  expected_volatility: number;
}
