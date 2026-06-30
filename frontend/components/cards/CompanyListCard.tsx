"use client";

import { Company, fmtCompactUSD, fmtNum } from "@/lib/types";
import { Card } from "./Common";

export function CompanyListCard({ companies }: { companies: Company[] }) {
  return (
    <Card title="Companies" subtitle={`${companies.length} listed`} accent="#c2710f">
      <div className="gen-scroll">
        <table className="gen-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Name</th>
              <th>Sector</th>
              <th className="num">Price</th>
              <th className="num">Mkt cap</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => (
              <tr key={c.symbol}>
                <td className="mono">{c.symbol}</td>
                <td className="gen-ellipsis">{c.company_name}</td>
                <td className="gen-muted">{c.sector}</td>
                <td className="num">{fmtNum(c.last_price)}</td>
                <td className="num nowrap">{fmtCompactUSD(c.market_cap)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
