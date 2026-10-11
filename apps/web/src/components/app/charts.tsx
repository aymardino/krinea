"use client";

import { useId, useState } from "react";
import { cn } from "@/lib/utils";

/* Small, dependency-free charts that follow the dataviz rules: thin marks, one
   axis, status colours only for statuses, labels in text ink, hover tooltips. */

export type Segment = { key: string; label: string; value: number; color: string };

/** 100 % stacked horizontal bar for a part-to-whole of statuses. */
export function StackedBar({ segments, total, className }: { segments: Segment[]; total: number; className?: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const shown = segments.filter((s) => s.value > 0);
  return (
    <div className={className}>
      <div className="flex h-5 w-full overflow-hidden rounded-md bg-muted" role="img" aria-label={shown.map((s) => `${s.label} ${s.value}`).join(", ")}>
        {shown.map((s, i) => (
          <div
            key={s.key}
            onMouseEnter={() => setHover(s.key)}
            onMouseLeave={() => setHover(null)}
            title={`${s.label}: ${s.value} (${total ? Math.round((s.value / total) * 100) : 0} %)`}
            style={{ width: `${total ? (s.value / total) * 100 : 0}%`, background: s.color, marginLeft: i ? 2 : 0 }}
            className={cn("h-full min-w-[2px] transition-opacity", hover && hover !== s.key && "opacity-50")}
          />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {segments.map((s) => (
          <li key={s.key} className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: s.color }} /><span className="text-foreground">{s.label}</span><span className="tabular-nums">{s.value}</span></li>
        ))}
      </ul>
    </div>
  );
}

/** Horizontal bars: one value per row, single hue, direct labels. */
export function RowBars({ rows, max, className, color = "var(--brand-500)" }: { rows: { label: string; value: number; hint?: string }[]; max?: number; className?: string; color?: string }) {
  const m = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className={cn("space-y-2", className)}>
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[minmax(0,140px)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate">{r.label}</span>
          <div className="h-2.5 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${Math.min(100, (r.value / m) * 100)}%`, background: color }} /></div>
          <span className="tabular-nums text-xs text-muted-foreground">{r.hint ?? r.value}</span>
        </li>
      ))}
    </ul>
  );
}

/** Vertical bars over time (one series), with a hover tooltip. */
export function TimeBars({ points, className, height = 120 }: { points: { label: string; value: number }[]; className?: string; height?: number }) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...points.map((p) => p.value));
  const w = 100 / Math.max(1, points.length);
  return (
    <div className={cn("relative", className)}>
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="h-[120px] w-full" role="img" aria-labelledby={id}>
        <title id={id}>Decisions per day</title>
        <line x1="0" x2="100" y1={height - 0.5} y2={height - 0.5} stroke="var(--border)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {points.map((p, i) => {
          const h = (p.value / max) * (height - 8);
          return (
            <rect key={p.label} x={i * w + w * 0.2} y={height - h} width={w * 0.6} height={h} rx="0.6"
              fill={hover === i ? "var(--brand-700)" : "var(--brand-500)"}
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
          );
        })}
      </svg>
      {hover !== null && points[hover] && (
        <div className="pointer-events-none absolute -top-1 left-1/2 -translate-x-1/2 rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-md">{points[hover].label}: <b>{points[hover].value}</b></div>
      )}
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground"><span>{points[0]?.label}</span><span>{points[points.length - 1]?.label}</span></div>
    </div>
  );
}
