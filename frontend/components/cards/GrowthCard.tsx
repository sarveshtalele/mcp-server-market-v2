"use client";

import { Growth, fmtPct, fmtUSD } from "@/lib/types";
import { Badge, Card, Stat, pctTone } from "./Common";

export function GrowthCard({ growth }: { growth: Growth }) {
  if (growth.error) {
    return (
      <Card title="Revenue growth" accent="#cf5b4e">
        <p className="gen-error">{growth.error}</p>
      </Card>
    );
  }
  return (
    <Card
      title={`${growth.symbol} — Growth`}
      subtitle={`Latest period ${growth.latest_period}`}
      accent="#2f8f5b"
    >
      <div className="gen-grid">
        <Stat label="Revenue" value={fmtUSD(growth.latest_revenue)} />
        <Stat label="Net profit" value={fmtUSD(growth.latest_net_profit)} />
      </div>
      <div className="gen-row gen-row--wrap">
        <Badge text={`Rev QoQ ${fmtPct(growth.revenue_qoq_pct)}`} tone={pctTone(growth.revenue_qoq_pct)} />
        <Badge text={`Rev YoY ${fmtPct(growth.revenue_yoy_pct)}`} tone={pctTone(growth.revenue_yoy_pct)} />
        <Badge text={`NP QoQ ${fmtPct(growth.net_profit_qoq_pct)}`} tone={pctTone(growth.net_profit_qoq_pct)} />
        <Badge text={`NP YoY ${fmtPct(growth.net_profit_yoy_pct)}`} tone={pctTone(growth.net_profit_yoy_pct)} />
      </div>
    </Card>
  );
}
