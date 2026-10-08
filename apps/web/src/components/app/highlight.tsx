"use client";

import { useMemo } from "react";

function kwRegex(kw: string): string {
  const parts = kw.split("*").map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const body = parts.join("\\w*");
  return kw.endsWith("*") ? `\\b${body}` : `\\b${body}\\b`;
}

/** Abstract with inclusion keywords in green and exclusion keywords in red. */
export function Highlight({ text, include, exclude }: { text: string; include: string[]; exclude: string[] }) {
  const nodes = useMemo(() => {
    const inc = include.filter(Boolean);
    const exc = exclude.filter(Boolean);
    if (!text || (!inc.length && !exc.length)) return [text];
    const all = [...new Set([...inc, ...exc])].sort((a, b) => b.length - a.length);
    const rx = new RegExp(all.map((k) => `(?:${kwRegex(k)})`).join("|"), "gi");
    const incRx = inc.map((k) => new RegExp(`^${kwRegex(k)}$`, "i"));
    const out: React.ReactNode[] = [];
    let last = 0;
    for (const m of text.matchAll(rx)) {
      const start = m.index ?? 0;
      if (start > last) out.push(text.slice(last, start));
      const word = m[0];
      const isInc = incRx.some((r) => r.test(word));
      out.push(<mark key={start} className={isInc ? "kw-include" : "kw-exclude"}>{word}</mark>);
      last = start + word.length;
    }
    if (last < text.length) out.push(text.slice(last));
    return out;
  }, [text, include, exclude]);
  return <>{nodes}</>;
}
