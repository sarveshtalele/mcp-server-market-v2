/**
 * Predefined agents — one-click analyst personas.
 *
 * Each agent is a templated prompt. Clicking it fills the composer with the
 * template (with a `<TICKER>`/`<SECTOR>` placeholder for the user to complete),
 * so the model runs a focused, multi-tool analysis for that persona.
 */
export interface AgentPreset {
  id: string;
  name: string;
  icon: string;
  tagline: string;
  /** Prompt template. `{q}` is where the user's subject goes. */
  template: string;
  /** Placeholder shown to the user for the subject. */
  placeholder: string;
}

export const AGENTS: AgentPreset[] = [
  {
    id: "valuation",
    name: "Valuation Analyst",
    icon: "◈",
    tagline: "Ratios, multiples & a verdict",
    template:
      "Act as a valuation analyst for {q}. Pull the company profile and latest " +
      "financial ratios, then judge whether its P/E and P/B look cheap or rich " +
      "versus its sector. End with a one-line valuation verdict.",
    placeholder: "ticker, e.g. AAPL",
  },
  {
    id: "growth",
    name: "Growth Scout",
    icon: "↗",
    tagline: "QoQ / YoY momentum",
    template:
      "Act as a growth analyst for {q}. Compute revenue and net-profit growth " +
      "(QoQ and YoY) and show the quarterly revenue trend. Say whether momentum " +
      "is accelerating or slowing.",
    placeholder: "ticker, e.g. NVDA",
  },
  {
    id: "screener",
    name: "Sector Screener",
    icon: "▤",
    tagline: "Rank a sector",
    template:
      "Act as a sector screener for the {q} sector. Rank the top 5 companies by " +
      "market cap, then call out the cheapest by P/E and the highest dividend yield.",
    placeholder: "sector, e.g. Technology",
  },
  {
    id: "compare",
    name: "Peer Comparator",
    icon: "⇄",
    tagline: "Head-to-head",
    template:
      "Act as an equity analyst and compare {q}. Put them side by side on market " +
      "cap, P/E, P/B, dividend yield, margin and ROE, and name the standout on each.",
    placeholder: "tickers, e.g. JPM, BAC, WFC",
  },
];

/** Build the composer text for an agent + subject. */
export function agentPrompt(agent: AgentPreset, subject: string): string {
  return agent.template.replace("{q}", subject.trim());
}
