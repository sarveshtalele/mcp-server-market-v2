"use client";

import React from "react";

export function Card({
  title,
  subtitle,
  accent,
  children,
}: {
  title: string;
  subtitle?: string;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="gen-card" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="gen-card__head">
        <span className="gen-card__title">{title}</span>
        {subtitle && <span className="gen-card__subtitle">{subtitle}</span>}
      </div>
      <div className="gen-card__body">{children}</div>
    </div>
  );
}

export function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="gen-stat">
      <span className="gen-stat__label">{label}</span>
      <span className="gen-stat__value">{value}</span>
    </div>
  );
}

export function Skeleton({ label = "Fetching data…" }: { label?: string }) {
  return (
    <div className="gen-card gen-card--loading">
      <div className="gen-skeleton-bar" />
      <div className="gen-skeleton-bar gen-skeleton-bar--short" />
      <span className="gen-card__loading-label">{label}</span>
    </div>
  );
}

export function Badge({ text, tone = "neutral" }: { text: string; tone?: string }) {
  return <span className={`gen-badge gen-badge--${tone}`}>{text}</span>;
}

export function pctTone(v: number | null | undefined): string {
  if (v == null) return "neutral";
  return v >= 0 ? "pos" : "neg";
}
