"use client";

import React from "react";

/**
 * Tiny, dependency-free markdown renderer for streamed assistant text.
 * Handles headings, bullet/numbered lists, tables, horizontal rules, bold,
 * italic, inline code and paragraphs — enough for the analyst's prose. Tool
 * results are rendered separately as cards.
 */
function inline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // **bold** before *italic* so the longer marker wins. Underscores are not
  // italic markers here on purpose: the model quotes field names like
  // net_profit_margin_pct, and treating those as emphasis mangles them.
  const regex = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`)/g;
  const parts = text.split(regex);
  parts.forEach((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      nodes.push(<strong key={i}>{p.slice(2, -2)}</strong>);
    } else if (p.length > 2 && p.startsWith("*") && p.endsWith("*")) {
      nodes.push(<em key={i}>{p.slice(1, -1)}</em>);
    } else if (p.startsWith("`") && p.endsWith("`")) {
      nodes.push(<code key={i}>{p.slice(1, -1)}</code>);
    } else if (p) {
      nodes.push(<React.Fragment key={i}>{p}</React.Fragment>);
    }
  });
  return nodes;
}

function splitRow(line: string): string[] {
  return line
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());
}
const isTableRow = (l: string) => /^\s*\|.*\|\s*$/.test(l);
const isSeparator = (l: string) => /^\s*\|?[\s:|-]+\|?\s*$/.test(l) && l.includes("-");

export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let table: string[] | null = null;

  const flush = () => {
    if (list) {
      const Tag = list.ordered ? "ol" : "ul";
      blocks.push(
        <Tag key={`l${blocks.length}`} className="md-list">
          {list.items.map((it, i) => (
            <li key={i}>{inline(it)}</li>
          ))}
        </Tag>,
      );
      list = null;
    }
    if (table) {
      const rows = table.filter((r) => !isSeparator(r)).map(splitRow);
      const [head, ...body] = rows;
      blocks.push(
        <div key={`t${blocks.length}`} className="md-tablewrap">
          <table className="md-table">
            {head && (
              <thead>
                <tr>{head.map((c, i) => <th key={i}>{inline(c)}</th>)}</tr>
              </thead>
            )}
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri}>{r.map((c, ci) => <td key={ci}>{inline(c)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      table = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();

    if (isTableRow(line)) {
      if (list) flush();
      if (!table) table = [];
      table.push(line);
      continue;
    } else if (table) {
      flush();
    }

    // `---` is a horizontal rule, not a paragraph. Without this it renders as
    // literal dashes in the middle of the answer.
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      flush();
      blocks.push(<hr key={`hr${blocks.length}`} className="md-hr" />);
      continue;
    }

    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    const bullet = /^[-*]\s+(.*)$/.exec(line);
    const numbered = /^\d+\.\s+(.*)$/.exec(line);

    if (h) {
      flush();
      const level = Math.min(h[1].length + 2, 6);
      const Tag = `h${level}` as keyof React.JSX.IntrinsicElements;
      blocks.push(
        <Tag key={`h${blocks.length}`} className="md-h">
          {inline(h[2])}
        </Tag>,
      );
    } else if (bullet) {
      if (!list || list.ordered) {
        flush();
        list = { ordered: false, items: [] };
      }
      list.items.push(bullet[1]);
    } else if (numbered) {
      if (!list || !list.ordered) {
        flush();
        list = { ordered: true, items: [] };
      }
      list.items.push(numbered[1]);
    } else if (line.trim() === "") {
      flush();
    } else {
      flush();
      blocks.push(
        <p key={`p${blocks.length}`} className="md-p">
          {inline(line)}
        </p>,
      );
    }
  }
  flush();
  return <div className="md">{blocks}</div>;
}
