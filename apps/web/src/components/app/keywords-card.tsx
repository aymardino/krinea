"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import { api, ApiError, type KeywordCounts, type Review } from "@/lib/api";
import { cn } from "@/lib/utils";

type Kind = "include" | "exclude";
type Lists = { [k in Kind]: string[] };
const EMPTY: Lists = { include: [], exclude: [] };

/** Keywords typed or pasted at once: commas, semicolons, tabs and line breaks all separate
 *  them, so a column copied from a spreadsheet or a list from a document goes in as is. */
export function splitKeywords(text: string): string[] {
  return text.split(/[,;\t\r\n]+/).map((s) => s.trim()).filter(Boolean);
}

/** One pair of keyword lists (green to include, red to exclude), editable in place. A click
 *  on a keyword adds it to the queue's filter, or takes it out. */
function KeywordLists({ title, lists, counts, editable, pending, picked, onSave, onPick }: {
  title?: string; lists: Lists; counts?: KeywordCounts | KeywordCounts["search"]; editable: boolean; pending: boolean;
  picked: string[]; onSave: (next: Lists) => void; onPick: (keyword: string) => void;
}) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const [draft, setDraft] = useState<{ [k in Kind]: string }>({ include: "", exclude: "" });
  const n = (kind: Kind, kw: string) => counts?.[kind].find((k) => k.keyword === kw)?.n;
  const isPicked = (kw: string) => picked.some((p) => p.toLowerCase() === kw.toLowerCase());
  const addText = (kind: Kind, text: string) => {
    const known = new Set(lists[kind].map((k) => k.toLowerCase()));
    const items: string[] = [];
    for (const k of splitKeywords(text)) {
      if (!known.has(k.toLowerCase())) { known.add(k.toLowerCase()); items.push(k); }
    }
    setDraft((d) => ({ ...d, [kind]: "" }));
    if (items.length) onSave({ ...lists, [kind]: [...lists[kind], ...items] });
  };
  const add = (kind: Kind) => addText(kind, draft[kind]);
  const remove = (kind: Kind, kw: string) => onSave({ ...lists, [kind]: lists[kind].filter((k) => k !== kw) });

  return (
    <div className="mt-3 first:mt-2">
      {title && <p className="text-xs font-medium text-foreground">{title}</p>}
      {(["include", "exclude"] as Kind[]).map((kind) => (
        <div key={kind} className="mt-2">
          <p className="text-[11px] font-medium text-muted-foreground">{t(kind === "include" ? "includeKw" : "excludeKw")}</p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {lists[kind].map((kw) => (
              <li key={kw} className={cn("inline-flex max-w-full items-center gap-1 rounded-md pl-1.5 text-xs", kind === "include" ? "bg-include-bg text-include" : "bg-exclude-bg text-exclude",
                                         !editable && "pr-1.5", isPicked(kw) && "ring-2 ring-current")}>
                <button type="button" className="truncate hover:underline" aria-pressed={isPicked(kw)}
                        title={t(isPicked(kw) ? "kwRemove" : "filterBy", { keyword: kw })} onClick={() => onPick(kw)}>{kw}</button>
                {n(kind, kw) !== undefined && <span className="tabular-nums opacity-70">{n(kind, kw)}</span>}
                {editable && (
                  <button type="button" aria-label={`${c("delete")} ${kw}`} className="rounded-r-md px-1 py-0.5 hover:bg-black/10" onClick={() => remove(kind, kw)} disabled={pending}><X className="size-3" /></button>
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
                onPaste={(e) => {
                  // A one-line field drops line breaks: a pasted list is split here instead.
                  const text = e.clipboardData.getData("text");
                  if (!/[\t\r\n]/.test(text)) return;
                  e.preventDefault();
                  addText(kind, `${draft[kind]}\n${text}`);
                }}
                disabled={pending}
              />
              <button type="submit" aria-label={c("save")} className="inline-flex size-7 items-center justify-center rounded-md border border-input text-muted-foreground hover:bg-muted" disabled={!draft[kind].trim() || pending}><Plus className="size-3.5" /></button>
            </form>
          )}
        </div>
      ))}
    </div>
  );
}

/** Highlight keywords, editable right where they are used (the screening rail). The review's
 *  own keywords apply to every record; when one search (imported file) is selected, its own
 *  keywords are shown too, and they are highlighted on the records that search found.
 *  Green ones mark text to include, red ones text to exclude; `*` is a wildcard. */
export function KeywordsCard({ review, counts, editable, picked = [], onPick, onChanged, search }: {
  review: Review; counts?: KeywordCounts; editable: boolean; picked?: string[]; onPick: (keyword: string) => void; onChanged: () => void;
  search?: { importId: string; label: string };
}) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const qc = useQueryClient();
  const general: Lists = { include: review.criteria.highlight_include, exclude: review.criteria.highlight_exclude };
  const bySearch = review.criteria.search_keywords ?? {};
  const own: Lists = search ? (bySearch[search.importId] ?? EMPTY) : EMPTY;
  const hasSearchKeywords = Object.values(bySearch).some((l) => l.include.length || l.exclude.length);
  const done = { onSuccess: () => { qc.invalidateQueries({ queryKey: ["keywords", review.id] }); onChanged(); toast.success(c("saved")); },
                 onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : c("error")) };

  const saveGeneral = useMutation({
    mutationFn: (next: Lists) => api.patch<Review>(`/reviews/${review.id}`, { criteria: { highlight_include: next.include, highlight_exclude: next.exclude } }),
    ...done,
  });
  const saveSearch = useMutation({
    mutationFn: (next: Lists) => api.put<Lists>(`/reviews/${review.id}/imports/${search!.importId}/keywords`, next),
    ...done,
  });

  const empty = !general.include.length && !general.exclude.length && !own.include.length && !own.exclude.length;
  if (!editable && empty && !hasSearchKeywords) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("keywordsTitle")}</p>
      <KeywordLists title={search ? t("kwReview") : undefined} lists={general} counts={counts} editable={editable} picked={picked}
                    pending={saveGeneral.isPending} onSave={(next) => saveGeneral.mutate(next)} onPick={onPick} />
      {search && (
        <div className="mt-4 border-t border-border pt-3">
          <KeywordLists key={search.importId} title={t("kwSearch", { file: search.label })} lists={own} counts={counts?.search} editable={editable} picked={picked}
                        pending={saveSearch.isPending} onSave={(next) => saveSearch.mutate(next)} onPick={onPick} />
          <p className="mt-2 text-[11px] text-muted-foreground">{t("kwSearchHint")}</p>
        </div>
      )}
      {!search && hasSearchKeywords && <p className="mt-3 text-[11px] text-muted-foreground">{t("kwSearchFilterHint")}</p>}
      {editable && <p className="mt-2 text-[11px] text-muted-foreground">{t("keywordHint")}</p>}
    </div>
  );
}
