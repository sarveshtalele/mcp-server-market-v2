"use client";

import React from "react";
import {
  Comparison,
  Company,
  Filing,
  Growth,
  Ratios,
  SectorRank,
  parseResult,
} from "@/lib/types";
import { CompanyCard } from "@/components/cards/CompanyCard";
import { CompanyListCard } from "@/components/cards/CompanyListCard";
import { RatioCard } from "@/components/cards/RatioCard";
import { GrowthCard } from "@/components/cards/GrowthCard";
import { ComparisonTable } from "@/components/cards/ComparisonTable";
import { SectorRankCard } from "@/components/cards/SectorRankCard";
import { TrendChart } from "@/components/cards/TrendChart";

/** Map an MCP tool name + raw JSON result to a rich card (or null). */
export function renderToolCard(
  name: string,
  result: string | undefined,
): React.ReactNode {
  if (!result) return null;
  switch (name) {
    case "get_company": {
      const c = parseResult<Company>(result);
      return c?.symbol ? <CompanyCard company={c} /> : null;
    }
    case "search_companies": {
      const list = parseResult<Company[]>(result);
      return Array.isArray(list) ? <CompanyListCard companies={list} /> : null;
    }
    case "get_filings": {
      const list = parseResult<Filing[]>(result);
      return Array.isArray(list) && list.length ? (
        <TrendChart filings={list} />
      ) : null;
    }
    case "calc_financial_ratios": {
      const r = parseResult<Ratios>(result);
      return r?.profitability ? <RatioCard ratios={r} /> : null;
    }
    case "calc_revenue_growth": {
      const g = parseResult<Growth>(result);
      return g ? <GrowthCard growth={g} /> : null;
    }
    case "compare_companies": {
      const c = parseResult<Comparison>(result);
      return c?.companies ? <ComparisonTable data={c} /> : null;
    }
    case "sector_ranking": {
      const s = parseResult<SectorRank>(result);
      return s?.ranking ? <SectorRankCard data={s} /> : null;
    }
    default:
      return null;
  }
}

// Friendly verb shown on the tool chip while running.
export const TOOL_LABEL: Record<string, string> = {
  get_company: "Looking up company",
  search_companies: "Searching companies",
  list_sectors: "Listing sectors",
  get_filings: "Fetching filings",
  get_latest_filing: "Fetching latest filing",
  calc_financial_ratios: "Computing ratios",
  calc_revenue_growth: "Computing growth",
  compare_companies: "Comparing companies",
  sector_ranking: "Ranking sector",
};
