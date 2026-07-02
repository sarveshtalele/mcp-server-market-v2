// Shapes returned by the MCP tools (mirrors backend core/schemas + calculations).

export interface Company {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  market: string;
  listing_date: string;
  par_value: number;
  shares_outstanding: number;
  last_price: number;
  market_cap: number;
  pe_ratio: number;
  pb_ratio: number;
  dividend_yield: number;
  is_active: boolean;
}

export interface Filing {
  filing_id: number;
  symbol: string;
  filing_type: string;
  fiscal_period: string;
  filing_date: string;
  revenue: number;
  net_profit: number;
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  operating_cash_flow: number;
  eps: number;
}

export interface Ratios {
  symbol: string;
  fiscal_period: string;
  profitability: Record<string, number | null>;
  leverage: Record<string, number | null>;
  efficiency: Record<string, number | null>;
  per_share: Record<string, number | null>;
  valuation: Record<string, number | null>;
}

export interface Growth {
  symbol: string;
  latest_period: string;
  latest_revenue: number;
  latest_net_profit: number;
  revenue_qoq_pct: number | null;
  net_profit_qoq_pct: number | null;
  revenue_yoy_pct: number | null;
  net_profit_yoy_pct: number | null;
  error?: string;
}

export interface ComparisonRow {
  symbol: string;
  company_name: string;
  sector: string;
  market_cap: number;
  last_price: number;
  pe_ratio: number;
  pb_ratio: number;
  dividend_yield_pct: number;
  net_profit_margin_pct: number | null;
  return_on_equity_pct: number | null;
}

export interface Comparison {
  companies: ComparisonRow[];
  highlights: Record<string, string | null>;
}

export interface SectorRank {
  metric: string;
  unit: string;
  order: string;
  ranking: { rank: number; symbol: string; company_name: string; value: number }[];
}

// Tool results arrive as JSON strings; parse defensively.
export function parseResult<T>(result: unknown): T | null {
  if (result == null) return null;
  if (typeof result === "object") return result as T;
  if (typeof result === "string") {
    try {
      return JSON.parse(result) as T;
    } catch {
      return null;
    }
  }
  return null;
}

export const fmtUSD = (n: number): string =>
  "$" + new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n);

// Compact USD for large amounts: $1.74 tn / $281.78 bn / $644.00 mn
export const fmtCompactUSD = (n: number): string => {
  const a = Math.abs(n);
  if (a >= 1e12) return `$${(n / 1e12).toFixed(2)} tn`;
  if (a >= 1e9) return `$${(n / 1e9).toFixed(2)} bn`;
  if (a >= 1e6) return `$${(n / 1e6).toFixed(2)} mn`;
  return "$" + new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n);
};

export const fmtPct = (n: number | null | undefined): string =>
  n == null ? "—" : `${n.toFixed(2)}%`;

export const fmtNum = (n: number | null | undefined, d = 2): string =>
  n == null ? "—" : n.toFixed(d);
