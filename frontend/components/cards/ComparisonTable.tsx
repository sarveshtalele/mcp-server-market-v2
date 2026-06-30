"use client";

import { Comparison, fmtCompactUSD, fmtNum, fmtPct } from "@/lib/types";
import { Card } from "./Common";

export function ComparisonTable({ data }: { data: Comparison }) {
  const h = data.highlights;
  return (
    <Card title="Company comparison" accent="#b5742a">
      <table className="gen-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th className="num">Mkt cap</th>
            <th className="num">P/E</th>
            <th className="num">P/B</th>
            <th className="num">Div %</th>
            <th className="num">Margin</th>
            <th className="num">ROE</th>
          </tr>
        </thead>
        <tbody>
          {data.companies.map((c) => (
            <tr key={c.symbol}>
              <td className="mono">{c.symbol}</td>
              <td className="num nowrap">{fmtCompactUSD(c.market_cap)}</td>
              <td className="num">{fmtNum(c.pe_ratio)}</td>
              <td className="num">{fmtNum(c.pb_ratio)}</td>
              <td className="num">{fmtPct(c.dividend_yield_pct)}</td>
              <td className="num">{fmtPct(c.net_profit_margin_pct)}</td>
              <td className="num">{fmtPct(c.return_on_equity_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="gen-highlights">
        <span>🏆 Largest: <b>{h.largest_by_market_cap ?? "—"}</b></span>
        <span>💸 Cheapest P/E: <b>{h.cheapest_by_pe ?? "—"}</b></span>
        <span>📈 Highest ROE: <b>{h.highest_roe ?? "—"}</b></span>
        <span>💰 Top yield: <b>{h.highest_dividend_yield ?? "—"}</b></span>
      </div>
    </Card>
  );
}
