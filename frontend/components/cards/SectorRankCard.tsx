"use client";

import { SectorRank, fmtNum } from "@/lib/types";
import { Card } from "./Common";

export function SectorRankCard({ data }: { data: SectorRank }) {
  return (
    <Card
      title="Sector ranking"
      subtitle={`By ${data.metric} (${data.order}) · ${data.unit}`}
      accent="#d99a1e"
    >
      <ol className="gen-rank">
        {data.ranking.map((r) => (
          <li key={r.symbol}>
            <span className="gen-rank__pos">{r.rank}</span>
            <span className="mono">{r.symbol}</span>
            <span className="gen-rank__name">{r.company_name}</span>
            <span className="gen-rank__val">{fmtNum(r.value)}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
