"use client";

import { useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Upload, Trash2, GitMerge, RotateCcw } from "lucide-react";
import { api, ApiError, type Candidate, type Duplicate, type ImportRow, type Job, type RecordPage } from "@/lib/api";
import { Link } from "@/i18n/navigation";
import { formatDate } from "@/lib/utils";
import { canEdit, canReview, useReview } from "@/components/app/review-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, Stat } from "@/components/ui/misc";

export default function DataPage() {
  const t = useTranslations("review.data");
  const c = useTranslations("common");
  const locale = useLocale();
  const qc = useQueryClient();
  const { review, refresh } = useReview();
  const rid = review.id;
  const editable = canEdit(review.my_role);
  const canResolve = canReview(review.my_role);      // reviewers settle duplicate pairs too
  const fileRef = useRef<HTMLInputElement>(null);
  const [source, setSource] = useState("");
  const [auto, setAuto] = useState(95);
  const [ask, setAsk] = useState(85);
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : c("error"));

  const imports = useQuery<ImportRow[]>({ queryKey: ["imports", rid], queryFn: () => api.get(`/reviews/${rid}/imports`) });
  const candidates = useQuery<Candidate[]>({ queryKey: ["candidates", rid], queryFn: () => api.get(`/reviews/${rid}/dedup/candidates`) });
  const duplicates = useQuery<Duplicate[]>({ queryKey: ["duplicates", rid], queryFn: () => api.get(`/reviews/${rid}/dedup/duplicates`) });
  const records = useQuery<RecordPage>({ queryKey: ["records", rid, "all-table"], queryFn: () => api.get(`/reviews/${rid}/records?stage=all&view=all&limit=200`) });
  const invalidateAll = () => { ["imports", "candidates", "duplicates", "records"].forEach((k) => qc.invalidateQueries({ queryKey: [k, rid] })); refresh(); };

  const upload = useMutation({
    mutationFn: async (files: FileList) => {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append("files", f));
      form.append("source_db", source);
      return api.upload<ImportRow[]>(`/reviews/${rid}/imports`, form);
    },
    onSuccess: (rows) => {
      rows.forEach((r) => r.error ? toast.error(`${r.filename}: ${r.error}`) : toast.success(t("imported", { n: r.n_records, file: r.filename })));
      invalidateAll();
      if (fileRef.current) fileRef.current.value = "";
    },
    onError,
  });
  const deleteImport = useMutation({ mutationFn: (id: string) => api.delete(`/reviews/${rid}/imports/${id}`), onSuccess: invalidateAll, onError });
  const dedup = useMutation({
    mutationFn: () => api.post<Job>(`/reviews/${rid}/dedup/run`, { auto_threshold: auto, review_threshold: ask }),
    onSuccess: (job) => { const r = job.result as { removed?: number; possible?: number }; toast.success(t("dedupDone", { removed: r.removed ?? 0, possible: r.possible ?? 0 })); invalidateAll(); },
    onError,
  });
  const resolve = useMutation({
    mutationFn: ({ id, action, keep }: { id: number; action: "merge" | "ignore"; keep?: number }) =>
      api.post(`/reviews/${rid}/dedup/candidates/${id}/${action}${keep ? `?keep=${keep}` : ""}`),
    onSuccess: invalidateAll,
    onError,
  });
  const rule = review.settings.keeper_rule ?? "complete";
  const restoreAll = useMutation({
    mutationFn: () => api.post<{ restored: number }>(`/reviews/${rid}/dedup/restore-all`),
    onSuccess: (r) => { toast.success(t("restoredAll", { n: r.restored })); invalidateAll(); },
    onError,
  });
  const restore = useMutation({ mutationFn: (id: number) => api.post(`/reviews/${rid}/records/${id}/restore`), onSuccess: invalidateAll, onError });

  const s = review.counts;
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label={t("imports")} value={imports.data?.length ?? 0} />
        <Stat label={t("records")} value={s.records} hint={`${s.unique} unique`} tone="brand" />
        <Stat label={t("duplicates")} value={s.duplicates} />
      </div>

      {editable && (
        <Card>
          <CardHeader><CardTitle>{t("upload")}</CardTitle><CardDescription>{t("uploadHint")}</CardDescription></CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5"><Label htmlFor="src">{t("sourceLabel")}</Label><Input id="src" className="w-56" placeholder="Scopus, PubMed…" value={source} onChange={(e) => setSource(e.target.value)} /></div>
            <input ref={fileRef} type="file" multiple accept=".ris,.bib,.txt,.nbib,.csv,.tsv,.xlsx,.xls" className="hidden" onChange={(e) => e.target.files?.length && upload.mutate(e.target.files)} />
            <Button onClick={() => fileRef.current?.click()} disabled={upload.isPending}><Upload />{t("import")}</Button>
          </CardContent>
        </Card>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold">{t("imports")}</h2>
        {!imports.data?.length ? (
          <EmptyState icon={<Upload />} title={t("upload")} description={t("uploadHint")} />
        ) : (
          <Table>
            <THead><TR><TH>File</TH><TH>{t("columns.source")}</TH><TH>Format</TH><TH className="text-right">Records</TH><TH className="text-right">{t("duplicates")}</TH><TH>Date</TH><TH /></TR></THead>
            <TBody>
              {imports.data.map((i) => (
                <TR key={i.id}>
                  <TD className="font-medium">{i.filename}</TD><TD>{i.source_db}</TD><TD><Badge variant="secondary">{i.format}</Badge></TD>
                  <TD className="text-right tabular-nums">{i.n_records}{i.n_skipped ? <span className="text-xs text-muted-foreground"> (+{i.n_skipped})</span> : null}</TD>
                  <TD className="text-right tabular-nums">{i.n_duplicates}</TD><TD className="text-muted-foreground">{formatDate(i.created_at, locale)}</TD>
                  <TD className="text-right">{editable && <Button size="xs" variant="ghost" onClick={() => confirm(t("deleteImport") + "?") && deleteImport.mutate(i.id)}><Trash2 /></Button>}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </section>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><GitMerge className="size-4 text-brand-600" />{t("duplicates")}</CardTitle><CardDescription>{t("dedupText")}</CardDescription></CardHeader>
        <CardContent className="space-y-6">
          {editable && (
            <div className="flex flex-wrap items-end gap-4">
              {/* The "ask" threshold can never pass the automatic one. */}
              <div className="space-y-1.5"><Label htmlFor="auto-th">{t("autoThreshold", { n: auto })}</Label><input id="auto-th" type="range" min={85} max={100} value={auto} onChange={(e) => { const v = +e.target.value; setAuto(v); if (ask > v) setAsk(v); }} className="block accent-brand-600" /></div>
              <div className="space-y-1.5"><Label htmlFor="ask-th">{t("askThreshold", { n: ask })}</Label><input id="ask-th" type="range" min={70} max={95} value={ask} onChange={(e) => { const v = +e.target.value; setAsk(v); if (auto < v) setAuto(v); }} className="block accent-brand-600" /></div>
              <Button onClick={() => dedup.mutate()} disabled={dedup.isPending || !s.records}>{t("runDedup")}</Button>
            </div>
          )}
          <ul className="space-y-1 rounded-lg bg-muted/60 px-4 py-3 text-sm text-ink-700">
            <li>{t("explainExact")}</li>
            <li>{t("explainAuto", { auto })}</li>
            <li>{t("explainAsk", { ask, auto })}</li>
            <li>{t("explainBelow", { ask })}</li>
          </ul>
          <p className="text-sm text-muted-foreground">
            {rule === "database" && review.settings.source_priority?.length
              ? t("keeperOrdered", { order: review.settings.source_priority.join(", ") })
              : rule === "file" ? t("keeperFiles") : t("keeperDefault")}{" "}
            <Link href={`/app/reviews/${rid}/settings#sources`} className="font-medium text-primary underline-offset-4 hover:underline">{t("keeperLink")}</Link>
          </p>
          <div>
            <h3 className="mb-2 text-sm font-semibold">{t("candidates")} <Badge variant="secondary">{candidates.data?.length ?? 0}</Badge></h3>
            {!candidates.data?.length ? <p className="text-sm text-muted-foreground">{t("noCandidates")}</p> : (
              <div className="space-y-3">
                {candidates.data.map((cd) => (
                  <div key={cd.id} className="rounded-xl border border-border p-4">
                    <p className="mb-3 text-xs text-muted-foreground">{Math.round(cd.score)}% · {cd.reason}</p>
                    <div className="grid gap-4 md:grid-cols-2">
                      {[cd.a, cd.b].map((r) => {
                        const suggested = cd.suggested_keep === r.id;
                        return (
                          <div key={r.id} className={`flex flex-col rounded-lg border p-3 text-sm ${suggested ? "border-brand-300 bg-brand-50" : "border-border"}`}>
                            <p className="font-medium">#{r.id} · {r.title}</p>
                            <p className="mt-1 text-xs text-muted-foreground">{[r.authors, r.year, r.journal, r.doi].filter(Boolean).join(" · ")}</p>
                            {r.source_db && <p className="mt-1 text-xs font-medium text-ink-700">{r.source_db}</p>}
                            {canResolve && (
                              <div className="mt-3 flex items-center gap-2">
                                <Button size="sm" variant={suggested ? "default" : "outline"} onClick={() => resolve.mutate({ id: cd.id, action: "merge", keep: r.id })} disabled={resolve.isPending}>{t("keepThis")}</Button>
                                {suggested && <span className="text-xs text-brand-700">{t("suggested")}</span>}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      {canResolve && <Button size="sm" variant="outline" onClick={() => resolve.mutate({ id: cd.id, action: "ignore" })} disabled={resolve.isPending}>{t("different")}</Button>}
                      <span className="text-xs text-muted-foreground">{t("keepHint")}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {!!duplicates.data?.length && (
            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">{t("removed")} <Badge variant="secondary">{duplicates.data.length}</Badge></h3>
                {editable && <Button size="sm" variant="outline" onClick={() => confirm(t("restoreAllConfirm", { n: duplicates.data!.length })) && restoreAll.mutate()} disabled={restoreAll.isPending}><RotateCcw />{t("restoreAll")}</Button>}
              </div>
              <Table>
                <THead><TR><TH>#</TH><TH>{t("columns.title")}</TH><TH>{t("columns.year")}</TH><TH>{t("columns.source")}</TH><TH>Match</TH><TH /></TR></THead>
                <TBody>
                  {duplicates.data.map((d) => (
                    <TR key={d.id}>
                      <TD className="text-muted-foreground">{d.id}</TD><TD>{d.title}<span className="block text-xs text-muted-foreground">{t("keptAs", { id: d.kept_id })}</span></TD>
                      <TD>{d.year}</TD><TD>{d.source_db}</TD><TD className="text-xs text-muted-foreground">{Math.round(d.score)}% · {d.reason}</TD>
                      <TD className="text-right">{editable && <Button size="xs" variant="ghost" onClick={() => restore.mutate(d.id)}><RotateCcw />{t("restore")}</Button>}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {!!records.data?.items.length && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">{t("records")} <span className="text-sm font-normal text-muted-foreground">({records.data.total})</span></h2>
          <Table>
            <THead><TR><TH>#</TH><TH>{t("columns.title")}</TH><TH>{t("columns.year")}</TH><TH>{t("columns.source")}</TH><TH>{t("columns.status")}</TH><TH>{t("columns.pdf")}</TH></TR></THead>
            <TBody>
              {records.data.items.map((r) => (
                <TR key={r.id} className={r.is_duplicate ? "opacity-50" : ""}>
                  <TD className="text-muted-foreground">{r.id}</TD>
                  <TD><span className="line-clamp-2">{r.title}</span><span className="block text-xs text-muted-foreground">{r.authors}</span></TD>
                  <TD>{r.year}</TD><TD className="text-xs">{r.source_db}</TD>
                  <TD>{r.is_duplicate ? <Badge variant="secondary">duplicate</Badge> : <StatusBadge status={r.ta_status} label={c(`decision.${r.ta_status}` as "decision.pending")} />}</TD>
                  <TD>{r.has_pdf ? "✓" : r.pdf_status === "not_retrieved" ? "✗" : ""}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </section>
      )}
    </div>
  );
}
