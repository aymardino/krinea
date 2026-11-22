"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bot, Check, ExternalLink, FileText, Search } from "lucide-react";
import { api, ApiError, type Extraction, type Field, type ImportRow, type Job, type LabelCount, type RecordPage, type StudyRecord as Rec } from "@/lib/api";
import { canReview, useReview } from "@/components/app/review-context";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, PageHeader } from "@/components/ui/misc";
import { JobProgress } from "@/components/app/job-progress";
import { useJob } from "@/lib/use-job";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MultiSelect } from "@/components/ui/multi-select";

// A value compared loosely with the options, as Krinea does (D-53): case, accents, spaces,
// hyphens and underscores aside.
const looseKey = (s: string) => s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[\s_-]+/g, " ").trim();
const asOption = (options: string[], v: string) => options.find((o) => looseKey(o) === looseKey(v)) ?? v;

function DoiInput({ onSave, pending }: { onSave?: (doi: string) => void; pending: boolean }) {
  const t = useTranslations("review.extraction");
  const c = useTranslations("common");
  const [doi, setDoi] = useState("");
  if (!onSave) return <p className="rounded-md border border-dashed border-input px-3 py-2 text-sm text-muted-foreground">{t("noDoi")}</p>;
  return (
    <div className="flex gap-2">
      <Input value={doi} onChange={(e) => setDoi(e.target.value)} placeholder={t("doiPlaceholder")} />
      <Button variant="outline" onClick={() => onSave(doi)} disabled={!doi.trim() || pending}>{c("save")}</Button>
    </div>
  );
}

function FieldInput({ f, value, onChange, search, doi, onDoi, doiPending }: {
  f: Field; value: string; onChange: (v: string) => void; search: string; doi: string; onDoi?: (doi: string) => void; doiPending: boolean;
}) {
  const t = useTranslations("review.extraction");
  // A "search" field fills itself with the study's search (D-49): nothing to type.
  if (f.kind === "search") return <p className="rounded-md border border-dashed border-input px-3 py-2 text-sm text-muted-foreground">{search || "—"}</p>;
  // A "doi" field is the link of the DOI of the study's citation (D-52); without one, the
  // reviewer can add it to the citation.
  if (f.kind === "doi") {
    if (!doi) return <DoiInput onSave={onDoi} pending={doiPending} />;
    return (
      <a className="flex items-center gap-1.5 break-all rounded-md border border-dashed border-input px-3 py-2 text-sm text-primary hover:underline" href={`https://doi.org/${doi}`} target="_blank" rel="noreferrer">
        https://doi.org/{doi}<ExternalLink className="size-3 shrink-0" />
      </a>
    );
  }
  if (f.kind === "enum" || f.kind === "yesno") {
    const opts = f.kind === "yesno" ? ["yes", "no"] : f.options;
    // An answer that is no option stays visible, to be kept or replaced.
    const chosen = value ? asOption(opts, value) : "";
    const offList = chosen !== "" && !opts.includes(chosen);
    return (
      <Select value={chosen || "__none"} onValueChange={(v) => onChange(v === "__none" ? "" : v)}>
        <SelectTrigger className={offList ? "text-maybe" : undefined}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="__none">—</SelectItem>
          {offList && <SelectItem value={chosen}>{t("offList", { value: chosen })}</SelectItem>}
          {opts.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
        </SelectContent>
      </Select>
    );
  }
  if (f.kind === "multi") {
    const chosen = [...new Set(value.split(/[,;]/).map((s) => s.trim()).filter(Boolean).map((x) => asOption(f.options, x)))];
    const extra = chosen.filter((x) => !f.options.includes(x));
    return (
      <div className="flex flex-wrap gap-3 rounded-md border border-input p-2">
        {f.options.map((o) => (
          <label key={o} className="inline-flex items-center gap-1.5 text-sm">
            <Checkbox checked={chosen.includes(o)} onCheckedChange={(ck) => onChange((ck ? [...chosen, o] : chosen.filter((x) => x !== o)).join(", "))} />{o}
          </label>
        ))}
        {extra.map((o) => (
          <label key={o} className="inline-flex items-center gap-1.5 text-sm text-maybe">
            <Checkbox checked onCheckedChange={() => onChange(chosen.filter((x) => x !== o).join(", "))} />{t("offList", { value: o })}
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
  const [search, setSearch] = useState("");
  // Files, labels and statuses can be picked several at once (none: no filter); a study shows
  // when it matches any file, any label and any status picked.
  const [fileIds, setFileIds] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [labelFilter, setLabelFilter] = useState<string[]>([]);
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : c("error"));

  const params = new URLSearchParams({ stage: "extract", view: "all", limit: "500", search });
  fileIds.forEach((f) => params.append("import_id", f));
  labelFilter.forEach((l) => params.append("label", l));
  const qs = params.toString();
  const pool = useQuery<RecordPage>({ queryKey: ["records", rid, "extract", search, fileIds, labelFilter], queryFn: () => api.get(`/reviews/${rid}/records?${qs}`) });
  const labelList = useQuery<LabelCount[]>({ queryKey: ["labels", rid], queryFn: () => api.get(`/reviews/${rid}/labels`) });
  const imports = useQuery<ImportRow[]>({ queryKey: ["imports", rid], queryFn: () => api.get(`/reviews/${rid}/imports`) });
  const list = useQuery<Extraction[]>({ queryKey: ["extractions", rid], queryFn: () => api.get(`/reviews/${rid}/extraction`) });
  const one = useQuery<Extraction>({ queryKey: ["extraction", rid, open], queryFn: () => api.get(`/reviews/${rid}/extraction/${open}`), enabled: open !== null && !!list.data?.some((e) => e.record_id === open) });
  const byRecord = useMemo(() => new Map((list.data ?? []).map((e) => [e.record_id, e])), [list.data]);
  // A DOI typed for a study without one goes into its citation, for every export (D-52).
  const setDoi = useMutation({
    mutationFn: (doi: string) => api.patch<Rec>(`/reviews/${rid}/records/${open}`, { doi }),
    onSuccess: () => { toast.success(c("saved")); qc.invalidateQueries({ queryKey: ["records", rid] }); },
    onError,
  });
  const invalidate = () => { qc.invalidateQueries({ queryKey: ["extractions", rid] }); qc.invalidateQueries({ queryKey: ["extraction", rid] }); refresh(); };

  useEffect(() => { if (one.data) setValues(one.data.values); else if (open !== null && !byRecord.has(open)) setValues({}); }, [one.data, open, byRecord]);

  // Extraction runs in the background: drafts are shown when the job ends.
  const runJob = useJob(rid, ["extract"], (job) => {
    const r = job.result as { ok?: number; failed?: number };
    if (job.status === "done") toast.success(t("runDone", { ok: r.ok ?? 0, failed: r.failed ?? 0 }));
    else toast.error(t("runFailed"), { description: job.error });
    invalidate();
  });
  const run = useMutation({
    mutationFn: (ids?: number[]) => api.post<Job>(`/reviews/${rid}/extraction/run`, { record_ids: ids ?? null }),
    onSuccess: runJob.follow,
    onError,
  });
  const running = run.isPending || runJob.running;
  const progress = running && <JobProgress job={runJob.job} label={t("running")} className="max-w-xl" />;
  const verify = useMutation({
    mutationFn: (id: number) => api.put<Extraction>(`/reviews/${rid}/extraction/${id}`, { values, quotes: one.data?.quotes ?? {} }),
    onSuccess: () => { toast.success(c("saved")); invalidate(); setOpen(null); },
    onError,
  });

  const all = pool.data?.items ?? [];
  const items = all.filter((r) => {
    const st = byRecord.get(r.id)?.status ?? "none";
    return !statuses.length || statuses.some((s) => (s === "nopdf" ? !r.has_pdf : st === s));
  });
  const filtered = search.trim() !== "" || fileIds.length > 0 || statuses.length > 0 || labelFilter.length > 0;
  const todo = items.filter((r) => r.has_pdf && !byRecord.has(r.id)).map((r) => r.id);
  const current: Rec | undefined = all.find((r) => r.id === open);
  const ex = one.data;
  // The fields of every study, and those of the search the study belongs to (D-48).
  const shownFields = fields.filter((f) => !f.searches?.length || f.searches.some((id) => (current?.found_in ?? []).includes(id)));
  // The search the study belongs to (the file of its kept copy under the file order), for a "search" field.
  const searchName = (current?.found_in ?? []).map((id) => imports.data?.find((i) => i.id === id)?.filename).filter(Boolean).join(", ");

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
            {editable && current.has_pdf && <Button variant="outline" onClick={() => run.mutate([current.id])} disabled={running}><Bot />{t("reExtract")}</Button>}
            {editable && <Button onClick={() => verify.mutate(current.id)} disabled={verify.isPending}><Check />{t("saveVerified")}</Button>}
          </>}
        />
        {progress}
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-4 rounded-xl border border-border bg-card p-5">
            <div className={`rounded-md px-3 py-2 text-sm ${Object.keys(flags).length ? "bg-maybe-bg text-maybe" : "bg-include-bg text-include"}`}>{Object.keys(flags).length ? t("flags", { errors: nErr, warnings: nWarn }) : t("noFlags")}</div>
            {ex?.error && <p className="rounded-md bg-exclude-bg px-3 py-2 text-sm text-exclude">{ex.error}</p>}
            {shownFields.map((f) => (
              <div key={f.name} className="space-y-1.5">
                <Label className="flex items-center gap-2">{f.label}{f.required && <span className="text-exclude">*</span>}<span className="text-xs font-normal text-muted-foreground">{f.kind}</span></Label>
                <FieldInput f={f} value={values[f.name] ?? ""} onChange={(v) => setValues({ ...values, [f.name]: v })} search={searchName}
                  doi={current.doi} onDoi={editable ? (d) => setDoi.mutate(d) : undefined} doiPending={setDoi.isPending} />
                {flags[f.name] && <p className={`text-xs ${flags[f.name][0] === "error" ? "text-exclude" : "text-maybe"}`}>{flags[f.name][1]}</p>}
                {ex?.quotes?.[f.name] && <p className="text-xs italic text-muted-foreground">↳ {ex.quotes[f.name]}</p>}
              </div>
            ))}
          </div>
          {/* On wide screens the paper stays in view, under the app header, while the form
              scrolls: 4.5rem from the top, 1rem from the bottom, less the card's tabs and padding. */}
          <div className="rounded-xl border border-border bg-card p-3 lg:sticky lg:top-[4.5rem] lg:self-start">
            <Tabs defaultValue={current.has_pdf ? "pdf" : "text"}>
              <TabsList><TabsTrigger value="pdf">{t("pdf")}</TabsTrigger><TabsTrigger value="text">{t("textTab")}</TabsTrigger></TabsList>
              <TabsContent value="pdf">{current.has_pdf ? <iframe title="pdf" src={api.url(`/reviews/${rid}/records/${current.id}/pdf`)} className="h-[75vh] w-full rounded-lg border border-border bg-white lg:h-[calc(100vh-10.25rem)]" /> : <p className="p-4 text-sm text-muted-foreground">{t("noPdf")}</p>}</TabsContent>
              <TabsContent value="text"><pre className="h-[75vh] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs leading-relaxed lg:h-[calc(100vh-10.25rem)]">{ex?.text_extracted || "—"}</pre></TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* With a filter on, the AI runs on the studies shown only. */}
      <PageHeader title={t("title")} description={t("text")} actions={editable && <Button onClick={() => run.mutate(filtered ? todo : undefined)} disabled={running || !todo.length}><Bot />{t("run")} <span className="opacity-70">({t("runHint", { n: todo.length })})</span></Button>} />
      {progress}
      {!!all.length || filtered ? (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:w-72"><Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><Input className="pl-8" placeholder={t("search")} value={search} onChange={(e) => setSearch(e.target.value)} /></div>
          {(imports.data?.length ?? 0) > 1 && (
            <MultiSelect className="w-full sm:w-64" ariaLabel={t("fileFilter")} allLabel={t("allFiles")} value={fileIds} onChange={setFileIds}
                         options={imports.data!.map((i) => ({ value: i.id, label: `${i.filename}${i.source_db ? ` · ${i.source_db}` : ""}` }))} />
          )}
          {!!labelList.data?.length && (
            <MultiSelect className="w-full sm:w-48" ariaLabel={t("labelFilter")} allLabel={t("allLabels")} value={labelFilter} onChange={setLabelFilter}
                         options={labelList.data.map((l) => ({ value: l.label, label: `${l.label} (${l.n})` }))} />
          )}
          <MultiSelect className="w-full sm:w-52" ariaLabel={t("statusFilter")} allLabel={t("allStatuses")} value={statuses} onChange={setStatuses}
                       options={[...(["none", "draft", "verified", "failed"] as const).map((s) => ({ value: s, label: t(`status.${s}`) })), { value: "nopdf", label: t("noPdfFilter") }]} />
          {filtered && <span className="text-sm text-muted-foreground">{t("shown", { n: items.length, total: all.length })}</span>}
        </div>
      ) : null}
      {!items.length ? <EmptyState icon={<FileText />} title={filtered ? t("noMatch") : t("empty")} /> : (
        <Table>
          <THead><TR><TH>#</TH><TH>{t("study")}</TH><TH>{t("pdf")}</TH><TH>{t("statusCol")}</TH><TH /></TR></THead>
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
