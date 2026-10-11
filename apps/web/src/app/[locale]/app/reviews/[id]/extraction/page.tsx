"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bot, Check, FileText } from "lucide-react";
import { api, ApiError, type Extraction, type Field, type Job, type RecordPage, type StudyRecord as Rec } from "@/lib/api";
import { canReview, useReview } from "@/components/app/review-context";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, PageHeader } from "@/components/ui/misc";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function FieldInput({ f, value, onChange }: { f: Field; value: string; onChange: (v: string) => void }) {
  if (f.kind === "enum" || f.kind === "yesno") {
    const opts = f.kind === "yesno" ? ["yes", "no"] : f.options;
    return (
      <Select value={value || "__none"} onValueChange={(v) => onChange(v === "__none" ? "" : v)}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem value="__none">—</SelectItem>{opts.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
      </Select>
    );
  }
  if (f.kind === "multi") {
    const chosen = value.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
    return (
      <div className="flex flex-wrap gap-3 rounded-md border border-input p-2">
        {f.options.map((o) => (
          <label key={o} className="inline-flex items-center gap-1.5 text-sm">
            <Checkbox checked={chosen.includes(o)} onCheckedChange={(ck) => onChange((ck ? [...chosen, o] : chosen.filter((x) => x !== o)).join(", "))} />{o}
          </label>
        ))}
      </div>
    );
  }
  if (f.kind === "sentences" || f.kind === "list") return <Textarea value={value} onChange={(e) => onChange(e.target.value)} className="min-h-[70px]" />;
  return <Input value={value} onChange={(e) => onChange(e.target.value)} />;
}

export default function ExtractionPage() {
  const t = useTranslations("review.extraction");
  const c = useTranslations("common");
  const qc = useQueryClient();
  const { review, refresh } = useReview();
  const rid = review.id;
  const editable = canReview(review.my_role);
  const fields = review.extraction_schema;
  const [open, setOpen] = useState<number | null>(null);
  const [values, setValues] = useState<{ [k: string]: string }>({});
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : c("error"));

  const pool = useQuery<RecordPage>({ queryKey: ["records", rid, "extract"], queryFn: () => api.get(`/reviews/${rid}/records?stage=extract&view=all&limit=500`) });
  const list = useQuery<Extraction[]>({ queryKey: ["extractions", rid], queryFn: () => api.get(`/reviews/${rid}/extraction`) });
  const one = useQuery<Extraction>({ queryKey: ["extraction", rid, open], queryFn: () => api.get(`/reviews/${rid}/extraction/${open}`), enabled: open !== null && !!list.data?.some((e) => e.record_id === open) });
  const byRecord = useMemo(() => new Map((list.data ?? []).map((e) => [e.record_id, e])), [list.data]);
  const invalidate = () => { qc.invalidateQueries({ queryKey: ["extractions", rid] }); qc.invalidateQueries({ queryKey: ["extraction", rid] }); refresh(); };

  useEffect(() => { if (one.data) setValues(one.data.values); else if (open !== null && !byRecord.has(open)) setValues({}); }, [one.data, open, byRecord]);

  const run = useMutation({
    mutationFn: (ids?: number[]) => api.post<Job>(`/reviews/${rid}/extraction/run`, { record_ids: ids ?? null }),
    onSuccess: (job) => { const r = job.result as { ok?: number; failed?: number }; toast.success(`${r.ok ?? 0} drafts, ${r.failed ?? 0} failed`); invalidate(); },
    onError,
  });
  const verify = useMutation({
    mutationFn: (id: number) => api.put<Extraction>(`/reviews/${rid}/extraction/${id}`, { values, quotes: one.data?.quotes ?? {} }),
    onSuccess: () => { toast.success(c("saved")); invalidate(); setOpen(null); },
    onError,
  });

  const items = pool.data?.items ?? [];
  const todo = items.filter((r) => r.has_pdf && !byRecord.has(r.id)).map((r) => r.id);
  const current: Rec | undefined = items.find((r) => r.id === open);
  const ex = one.data;

  if (open !== null && current) {
    const flags = ex?.flags ?? {};
    const nErr = Object.values(flags).filter((f) => f[0] === "error").length;
    const nWarn = Object.values(flags).length - nErr;
    return (
      <div className="space-y-4">
        <PageHeader
          title={current.title}
          description={[current.authors, current.year, current.journal].filter(Boolean).join(" · ")}
          actions={<>
            <Button variant="outline" onClick={() => setOpen(null)}>{c("close")}</Button>
            {editable && current.has_pdf && <Button variant="outline" onClick={() => run.mutate([current.id])} disabled={run.isPending}><Bot />{t("reExtract")}</Button>}
            {editable && <Button onClick={() => verify.mutate(current.id)} disabled={verify.isPending}><Check />{t("saveVerified")}</Button>}
          </>}
        />
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-4 rounded-xl border border-border bg-card p-5">
            <div className={`rounded-md px-3 py-2 text-sm ${Object.keys(flags).length ? "bg-maybe-bg text-maybe" : "bg-include-bg text-include"}`}>{Object.keys(flags).length ? t("flags", { errors: nErr, warnings: nWarn }) : t("noFlags")}</div>
            {ex?.error && <p className="rounded-md bg-exclude-bg px-3 py-2 text-sm text-exclude">{ex.error}</p>}
            {fields.map((f) => (
              <div key={f.name} className="space-y-1.5">
                <Label className="flex items-center gap-2">{f.label}{f.required && <span className="text-exclude">*</span>}<span className="text-xs font-normal text-muted-foreground">{f.kind}</span></Label>
                <FieldInput f={f} value={values[f.name] ?? ""} onChange={(v) => setValues({ ...values, [f.name]: v })} />
                {flags[f.name] && <p className={`text-xs ${flags[f.name][0] === "error" ? "text-exclude" : "text-maybe"}`}>{flags[f.name][1]}</p>}
                {ex?.quotes?.[f.name] && <p className="text-xs italic text-muted-foreground">↳ {ex.quotes[f.name]}</p>}
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <Tabs defaultValue={current.has_pdf ? "pdf" : "text"}>
              <TabsList><TabsTrigger value="pdf">{t("pdf")}</TabsTrigger><TabsTrigger value="text">{t("textTab")}</TabsTrigger></TabsList>
              <TabsContent value="pdf">{current.has_pdf ? <iframe title="pdf" src={api.url(`/reviews/${rid}/records/${current.id}/pdf`)} className="h-[75vh] w-full rounded-lg border border-border bg-white" /> : <p className="p-4 text-sm text-muted-foreground">{t("noPdf")}</p>}</TabsContent>
              <TabsContent value="text"><pre className="h-[75vh] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs leading-relaxed">{ex?.text_extracted || "—"}</pre></TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("text")} actions={editable && <Button onClick={() => run.mutate(undefined)} disabled={run.isPending || !todo.length}><Bot />{t("run")} <span className="opacity-70">({t("runHint", { n: todo.length })})</span></Button>} />
      {!items.length ? <EmptyState icon={<FileText />} title={t("empty")} /> : (
        <Table>
          <THead><TR><TH>#</TH><TH>Study</TH><TH>{t("pdf")}</TH><TH>Status</TH><TH /></TR></THead>
          <TBody>
            {items.map((r) => {
              const e = byRecord.get(r.id);
              const st = e?.status ?? "none";
              return (
                <TR key={r.id}>
                  <TD className="text-muted-foreground">{r.id}</TD>
                  <TD><span className="line-clamp-2 font-medium">{r.title}</span><span className="block text-xs text-muted-foreground">{[r.authors, r.year].filter(Boolean).join(" · ")}</span></TD>
                  <TD>{r.has_pdf ? "✓" : "—"}</TD>
                  <TD><Badge variant={st === "verified" ? "include" : st === "draft" ? "maybe" : st === "failed" ? "exclude" : "pending"}>{t(`status.${st}` as "status.none")}</Badge></TD>
                  <TD className="text-right"><Button size="sm" variant={st === "none" ? "ghost" : "outline"} onClick={() => setOpen(r.id)}>{t("verify")}</Button></TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}
    </div>
  );
}
