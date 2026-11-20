"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil } from "lucide-react";
import { api, ApiError, type ImportRow, type Review, type SearchCriteria } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";

const FIELDS = ["question", "inclusion", "exclusion"] as const;
const EMPTY: SearchCriteria = { question: "", inclusion: "", exclusion: "" };

/** The sub-question and criteria of one search (imported file), when a review runs one search
 *  per sub-question (D-47). Shown while screening the records of that search, editable by the
 *  review's administrators; the AI gets them with the review's own criteria. */
function SearchCriteriaBlock({ review, importId, name, editable, onChanged }: { review: Review; importId: string; name: string; editable: boolean; onChanged: () => void }) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const saved = review.criteria.search_criteria?.[importId] ?? EMPTY;
  const has = FIELDS.some((f) => saved[f]?.trim());
  const [draft, setDraft] = useState<SearchCriteria | null>(null);
  const save = useMutation({
    mutationFn: (next: SearchCriteria) => api.put<SearchCriteria>(`/reviews/${review.id}/imports/${importId}/criteria`, next),
    onSuccess: () => { setDraft(null); onChanged(); toast.success(c("saved")); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : c("error")),
  });
  const label = { question: t("searchQuestion"), inclusion: t("searchInclusion"), exclusion: t("searchExclusion") };

  if (draft) {
    return (
      <form className="mt-2 space-y-2" onSubmit={(e) => { e.preventDefault(); save.mutate(draft); }}>
        <p className="truncate text-xs font-medium text-foreground" title={name}>{name}</p>
        {FIELDS.map((f) => (
          <label key={f} className="block text-[11px] text-muted-foreground">{label[f]}
            <Textarea className="mt-1 min-h-16 text-xs" value={draft[f]} onChange={(e) => setDraft({ ...draft, [f]: e.target.value })} disabled={save.isPending} />
          </label>
        ))}
        <div className="flex gap-2">
          <Button type="submit" size="xs" disabled={save.isPending}>{c("save")}</Button>
          <Button type="button" size="xs" variant="ghost" onClick={() => setDraft(null)} disabled={save.isPending}>{c("cancel")}</Button>
        </div>
      </form>
    );
  }
  if (!has && !editable) return null;
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs font-medium text-foreground" title={name}>{name}</p>
        {editable && (
          <button type="button" className="inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-primary hover:underline" onClick={() => setDraft({ ...EMPTY, ...saved })}>
            <Pencil className="size-3" />{has ? t("searchCriteriaEdit") : t("searchCriteriaAdd")}
          </button>
        )}
      </div>
      {has ? (
        <dl className="mt-1.5 space-y-1.5 text-xs">
          {FIELDS.filter((f) => saved[f]?.trim()).map((f) => (
            <div key={f}><dt className="text-[11px] font-medium text-muted-foreground">{label[f]}</dt><dd className="whitespace-pre-line leading-snug">{saved[f]}</dd></div>
          ))}
        </dl>
      ) : <p className="mt-1 text-[11px] text-muted-foreground">{t("searchCriteriaNone")}</p>}
    </div>
  );
}

/** The criteria of the searches that the record on screen belongs to (or of the file the list
 *  is filtered on). Hidden when no search has criteria and the member cannot add any. */
export function SearchCriteriaCard({ review, importIds, imports, editable, onChanged }: { review: Review; importIds: string[]; imports: ImportRow[]; editable: boolean; onChanged: () => void }) {
  const t = useTranslations("review.screening");
  const ids = importIds.filter((id) => imports.some((i) => i.id === id));
  const any = ids.some((id) => FIELDS.some((f) => review.criteria.search_criteria?.[id]?.[f]?.trim()));
  if (!ids.length || (!any && !editable)) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("searchCriteriaTitle")}</p>
      {ids.map((id) => (
        <SearchCriteriaBlock key={id} review={review} importId={id} name={imports.find((i) => i.id === id)?.filename ?? id} editable={editable} onChanged={onChanged} />
      ))}
      <p className="mt-3 text-[11px] text-muted-foreground">{t("searchCriteriaHint")}</p>
    </div>
  );
}
