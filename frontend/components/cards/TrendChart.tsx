"use client";

import { Filing, fmtUSD } from "@/lib/types";
import { Card } from "./Common";

/**
 * Revenue (bars) + net-profit (line) trend across quarterly filings.
 * Pure inline SVG — no chart dependency.
 */
export function TrendChart({ filings }: { filings: Filing[] }) {
  const q = filings
    .filter((f) => f.filing_type === "Quarterly")
    .sort((a, b) => a.fiscal_period.localeCompare(b.fiscal_period));

  if (q.length === 0) {
    return (
      <Card title="Revenue trend" accent="#e08a1e">
        <p className="gen-error">No quarterly filings to chart.</p>
      </Card>
    );
  }

  const W = 520;
  const H = 220;
  const padX = 36;
  const padTop = 16;
  const padBottom = 34;
  const plotW = W - padX * 2;
  const plotH = H - padTop - padBottom;

  const maxVal = Math.max(...q.map((f) => Math.max(f.revenue, f.net_profit)), 1);
  const n = q.length;
  const slot = plotW / n;
  const barW = Math.min(slot * 0.55, 38);

  const y = (v: number) => padTop + plotH - (v / maxVal) * plotH;
  const xCenter = (i: number) => padX + slot * i + slot / 2;

  const profitPts = q
    .map((f, i) => `${xCenter(i).toFixed(1)},${y(f.net_profit).toFixed(1)}`)
    .join(" ");

  const symbol = q[0].symbol;
  const gridLines = [0.25, 0.5, 0.75, 1].map((t) => padTop + plotH - t * plotH);

  return (
    <Card title={`${symbol} — Revenue trend`} subtitle={`${n} quarters · USD`} accent="#e08a1e">
      <svg viewBox={`0 0 ${W} ${H}`} className="gen-chart" role="img"
           aria-label={`${symbol} quarterly revenue and net profit`}>
        {/* grid */}
        {gridLines.map((gy, i) => (
          <line key={i} x1={padX} x2={W - padX} y1={gy} y2={gy}
                stroke="rgba(170,130,70,0.20)" strokeWidth="1" />
        ))}
        {/* revenue bars */}
        {q.map((f, i) => {
          const by = y(f.revenue);
          return (
            <rect key={f.fiscal_period} x={xCenter(i) - barW / 2} y={by}
                  width={barW} height={padTop + plotH - by}
                  rx="3" fill="#e08a1e" opacity="0.85">
              <title>{`${f.fiscal_period} revenue: ${fmtUSD(f.revenue)}`}</title>
            </rect>
          );
        })}
        {/* net-profit line */}
        <polyline points={profitPts} fill="none" stroke="#2f8f5b" strokeWidth="2.5" />
        {q.map((f, i) => (
          <circle key={`p${i}`} cx={xCenter(i)} cy={y(f.net_profit)} r="3.2" fill="#2f8f5b">
            <title>{`${f.fiscal_period} net profit: ${fmtUSD(f.net_profit)}`}</title>
          </circle>
        ))}
        {/* x labels */}
        {q.map((f, i) => (
          <text key={`x${i}`} x={xCenter(i)} y={H - 12} textAnchor="middle"
                fontSize="9" fill="#8a7657">
            {f.fiscal_period.replace("20", "'")}
          </text>
        ))}
      </svg>
      <div className="gen-legend">
        <span><i className="gen-legend__swatch" style={{ background: "#e08a1e" }} /> Revenue</span>
        <span><i className="gen-legend__swatch" style={{ background: "#2f8f5b" }} /> Net profit</span>
      </div>
    </Card>
  );
}
