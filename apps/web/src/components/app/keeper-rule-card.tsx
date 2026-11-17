"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowDown, ArrowUp } from "lucide-react";
import { api, ApiError, type ImportRow, type Review, type SourceCount } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Rule = "complete" | "file" | "database";
const RULES: Rule[] = ["complete", "file", "database"];

/** An ordered list: arrows to move one step, or type a rank to move straight there. */
function OrderList({ ids, label, detail, editable, onChange }: {
  ids: string[]; label: (id: string) => string; detail: (id: string) => string; editable: boolean; onChange: (next: string[]) => void;
}) {
  const t = useTranslations("review.settings");
  const moveTo = (from: number, to: number) => {
    if (to < 0 || to >= ids.length || to === from) return;
    const next = [...ids];
    const [x] = next.splice(from, 1);
    next.splice(to, 0, x);
    onChange(next);
  };
  return (
    <ol className="divide-y divide-border rounded-lg border border-border">
      {ids.map((id, i) => (
        <li key={id} className="flex items-center gap-3 px-3 py-2 text-sm">
          {editable ? (
            <input
              key={`${id}-${i}`}
              type="number" min={1} max={ids.length} defaultValue={i + 1} aria-label={`${t("rank")} ${label(id)}`}
              className="h-7 w-12 rounded-md border border-input bg-background px-1.5 text-center text-xs tabular-nums"
              onBlur={(e) => moveTo(i, Number(e.target.value) - 1)}
              onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
            />
          ) : <span className="w-6 text-right tabular-nums text-muted-foreground">{i + 1}</span>}
          <span className="min-w-0 flex-1 truncate font-medium">{label(id)}</span>
          <span className="shrink-0 text-xs text-muted-foreground">{detail(id)}</span>
          {editable && (
            <span className="flex shrink-0 gap-1">
              <Button size="xs" variant="ghost" aria-label={t("moveUp")} onClick={() => moveTo(i, i - 1)} disabled={i === 0}><ArrowUp /></Button>
              <Button size="xs" variant="ghost" aria-label={t("moveDown")} onClick={() => moveTo(i, i + 1)} disabled={i === ids.length - 1}><ArrowDown /></Button>
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

/** Which record a review keeps among duplicates: the most complete one (default), or the one
 *  from the first imported file, or from the first database, in an order the team chooses. */
export function KeeperRuleCard({ review, editable, onSaved }: { review: Review; editable: boolean; onSaved: (r: Review) => void }) {
  const t = useTranslations("review.settings");
  const c = useTranslations("common");
  const qc = useQueryClient();
  const rid = review.id;
  const saved = review.settings;
  const imports = useQuery<ImportRow[]>({ queryKey: ["imports", rid], queryFn: () => api.get(`/reviews/${rid}/imports`) });
  const sources = useQuery<SourceCount[]>({ queryKey: ["sources", rid], queryFn: () => api.get(`/reviews/${rid}/sources`) });
  const [rule, setRule] = useState<Rule>(saved.keeper_rule ?? "complete");
  const [files, setFiles] = useState<string[] | null>(null);
  const [dbs, setDbs] = useState<string[] | null>(null);

  // Saved orders first, then whatever was imported since, in import order or by frequency.
  const savedFiles = (saved.file_priority ?? []).filter((id) => imports.data?.some((i) => i.id === id));
  const fileOrder = files ?? [...savedFiles, ...(imports.data ?? []).map((i) => i.id).filter((id) => !savedFiles.includes(id))];
  const savedDbs = saved.source_priority ?? [];
  const dbOrder = dbs ?? [...savedDbs, ...(sources.data ?? []).map((s) => s.source).filter((s) => !savedDbs.some((o) => o.toLowerCase() === s.toLowerCase()))];
  const imp = (id: string) => imports.data?.find((i) => i.id === id);

  const save = useMutation({
    mutationFn: () => api.patch<Review>(`/reviews/${rid}`, {
      settings: { keeper_rule: rule, ...(rule === "file" ? { file_priority: fileOrder } : {}), ...(rule === "database" ? { source_priority: dbOrder } : {}) },
    }),
    onSuccess: (r) => { qc.setQueryData(["review", rid], r); setFiles(null); setDbs(null); onSaved(r); toast.success(c("saved")); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : c("error")),
  });

  return (
    <Card id="sources" className="scroll-mt-20">
      <CardHeader><CardTitle>{t("keepTitle")}</CardTitle><CardDescription>{t("keepHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <fieldset className="grid gap-2 md:grid-cols-3">
          <legend className="sr-only">{t("keepTitle")}</legend>
          {RULES.map((r) => (
            <label key={r} className={cn("flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm", rule === r ? "border-brand-300 bg-brand-50" : "border-border", !editable && "cursor-default")}>
              <input type="radio" name="keeper-rule" value={r} checked={rule === r} onChange={() => setRule(r)} disabled={!editable} className="mt-0.5 accent-brand-600" />
              <span><span className="block font-medium">{t(`rule.${r}`)}</span><span className="mt-0.5 block text-xs text-muted-foreground">{t(`rule.${r}Hint`)}</span></span>
            </label>
          ))}
        </fieldset>
        {rule === "file" && (fileOrder.length
          ? <OrderList ids={fileOrder} label={(id) => imp(id)?.filename ?? id} detail={(id) => [imp(id)?.source_db, t("sourcesCount", { n: imp(id)?.n_records ?? 0 })].filter(Boolean).join(" · ")} editable={editable} onChange={setFiles} />
          : <p className="text-sm text-muted-foreground">{t("filesNone")}</p>)}
        {rule === "database" && (dbOrder.length
          ? <OrderList ids={dbOrder} label={(s) => s} detail={(s) => t("sourcesCount", { n: sources.data?.find((x) => x.source.toLowerCase() === s.toLowerCase())?.n ?? 0 })} editable={editable} onChange={setDbs} />
          : <p className="text-sm text-muted-foreground">{t("sourcesNone")}</p>)}
        <p className="text-sm text-muted-foreground">{t("keepNext")}</p>
        {editable && <Button onClick={() => save.mutate()} disabled={save.isPending}>{c("save")}</Button>}
      </CardContent>
    </Card>
  );
}
