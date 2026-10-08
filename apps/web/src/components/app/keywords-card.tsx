"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import { api, ApiError, type KeywordCounts, type Review } from "@/lib/api";
import { cn } from "@/lib/utils";

type Kind = "include" | "exclude";

/** Highlight keywords, editable right where they are used (the screening rail).
 *  Green ones mark text to include, red ones text to exclude; `*` is a wildcard. */
export function KeywordsCard({ review, counts, editable, onPick, onChanged }: {
  review: Review; counts?: KeywordCounts; editable: boolean; onPick: (keyword: string) => void; onChanged: () => void;
}) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const qc = useQueryClient();
  const [draft, setDraft] = useState<{ [k in Kind]: string }>({ include: "", exclude: "" });
  const lists: { [k in Kind]: string[] } = { include: review.criteria.highlight_include, exclude: review.criteria.highlight_exclude };
  const n = (kind: Kind, kw: string) => counts?.[kind].find((k) => k.keyword === kw)?.n;

  const save = useMutation({
    mutationFn: (next: { [k in Kind]: string[] }) =>
      api.patch<Review>(`/reviews/${review.id}`, { criteria: { highlight_include: next.include, highlight_exclude: next.exclude } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["keywords", review.id] }); onChanged(); toast.success(c("saved")); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : c("error")),
  });
  const add = (kind: Kind) => {
    const value = draft[kind].trim().replace(/,+$/, "").trim();
    if (!value) return;
    const items = value.split(",").map((s) => s.trim()).filter(Boolean);
    const next = { ...lists, [kind]: Array.from(new Set([...lists[kind], ...items])) };
    setDraft((d) => ({ ...d, [kind]: "" }));
    save.mutate(next);
  };
  const remove = (kind: Kind, kw: string) => save.mutate({ ...lists, [kind]: lists[kind].filter((k) => k !== kw) });

  if (!editable && !lists.include.length && !lists.exclude.length) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("keywordsTitle")}</p>
      {(["include", "exclude"] as Kind[]).map((kind) => (
        <div key={kind} className="mt-3">
          <p className="text-[11px] font-medium text-muted-foreground">{t(kind === "include" ? "includeKw" : "excludeKw")}</p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {lists[kind].map((kw) => (
              <li key={kw} className={cn("inline-flex max-w-full items-center gap-1 rounded-md pl-1.5 text-xs", kind === "include" ? "bg-include-bg text-include" : "bg-exclude-bg text-exclude", !editable && "pr-1.5")}>
                <button type="button" className="truncate hover:underline" title={t("filterBy", { keyword: kw })} onClick={() => onPick(kw.replace("*", ""))}>{kw}</button>
                {n(kind, kw) !== undefined && <span className="tabular-nums opacity-70">{n(kind, kw)}</span>}
                {editable && (
                  <button type="button" aria-label={`${c("delete")} ${kw}`} className="rounded-r-md px-1 py-0.5 hover:bg-black/10" onClick={() => remove(kind, kw)} disabled={save.isPending}><X className="size-3" /></button>
                )}
              </li>
            ))}
            {!lists[kind].length && !editable && <li className="text-xs text-muted-foreground">{c("none")}</li>}
          </ul>
          {editable && (
            <form className="mt-1.5 flex gap-1" onSubmit={(e) => { e.preventDefault(); add(kind); }}>
              <input
                className={cn("h-7 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2", kind === "include" ? "focus-visible:ring-include/40" : "focus-visible:ring-exclude/40")}
                placeholder={t(kind === "include" ? "addInclude" : "addExclude")}
                value={draft[kind]}
                onChange={(e) => setDraft((d) => ({ ...d, [kind]: e.target.value }))}
                disabled={save.isPending}
              />
              <button type="submit" aria-label={c("save")} className="inline-flex size-7 items-center justify-center rounded-md border border-input text-muted-foreground hover:bg-muted" disabled={!draft[kind].trim() || save.isPending}><Plus className="size-3.5" /></button>
            </form>
          )}
        </div>
      ))}
      {editable && <p className="mt-2 text-[11px] text-muted-foreground">{t("keywordHint")}</p>}
    </div>
  );
}
