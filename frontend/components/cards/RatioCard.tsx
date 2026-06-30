"use client";

import { Ratios, fmtNum, fmtPct } from "@/lib/types";
import { Card, Stat } from "./Common";

export function RatioCard({ ratios }: { ratios: Ratios }) {
  const p = ratios.profitability;
  const l = ratios.leverage;
  const e = ratios.efficiency;
  const v = ratios.valuation;
  return (
    <Card
      title={`${ratios.symbol} — Financial ratios`}
      subtitle={`Period ${ratios.fiscal_period}`}
      accent="#c98a1f"
    >
      <div className="gen-section-label">Profitability</div>
      <div className="gen-grid">
        <Stat label="Net margin" value={fmtPct(p.net_profit_margin_pct)} />
        <Stat label="ROE" value={fmtPct(p.return_on_equity_pct)} />
        <Stat label="ROA" value={fmtPct(p.return_on_assets_pct)} />
      </div>
      <div className="gen-section-label">Leverage</div>
      <div className="gen-grid">
        <Stat label="Debt / Equity" value={fmtNum(l.debt_to_equity)} />
        <Stat label="Equity ratio" value={fmtNum(l.equity_ratio)} />
        <Stat label="Liab / Assets" value={fmtNum(l.liabilities_to_assets)} />
      </div>
      <div className="gen-section-label">Efficiency &amp; valuation</div>
      <div className="gen-grid">
        <Stat label="Asset turnover" value={fmtNum(e.asset_turnover)} />
        <Stat label="OCF margin" value={fmtPct(e.operating_cash_flow_margin_pct)} />
        <Stat label="P/E" value={fmtNum(v.pe_ratio)} />
        <Stat label="P/B" value={fmtNum(v.pb_ratio)} />
        <Stat label="Div. yield" value={fmtPct(v.dividend_yield_pct)} />
      </div>
    </Card>
  );
}
