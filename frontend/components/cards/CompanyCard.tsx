"use client";

import { Company, fmtCompactUSD, fmtNum, fmtPct } from "@/lib/types";
import { Badge, Card, Stat } from "./Common";

export function CompanyCard({ company }: { company: Company }) {
  return (
    <Card
      title={`${company.symbol} · ${company.company_name}`}
      subtitle={`${company.sector} — ${company.industry}`}
      accent="#e08a1e"
    >
      <div className="gen-row">
        <Badge text={company.market} tone="info" />
        <Badge text={company.is_active ? "Active" : "Suspended"} tone={company.is_active ? "pos" : "neg"} />
      </div>
      <div className="gen-grid">
        <Stat label="Last price" value={`$${fmtNum(company.last_price)}`} />
        <Stat label="Market cap" value={fmtCompactUSD(company.market_cap)} />
        <Stat label="P/E" value={fmtNum(company.pe_ratio)} />
        <Stat label="P/B" value={fmtNum(company.pb_ratio)} />
        <Stat label="Dividend yield" value={fmtPct(company.dividend_yield)} />
        <Stat label="Shares out." value={fmtCompactUSD(company.shares_outstanding).replace("$", "")} />
      </div>
    </Card>
  );
}
