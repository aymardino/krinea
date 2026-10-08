"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bot, ChevronLeft, ChevronRight, ExternalLink, FileText, Search, Sparkles, Tag, Upload, XCircle } from "lucide-react";
import { api, ApiError, type Job, type KeywordCounts, type StudyRecord, type RecordPage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { cn, formatDuration } from "@/lib/utils";
import { canEdit, canReview, useReview } from "@/components/app/review-context";
import { Highlight } from "@/components/app/highlight";
import { AiCard } from "@/components/app/ai-card";
import { KeywordsCard } from "@/components/app/keywords-card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, Kbd, Progress } from "@/components/ui/misc";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type Stage = "ta" | "ft";
const VIEWS: { [k in Stage]: string[] } = {
  ta: ["todo", "mine_include", "mine_maybe", "mine_exclude", "conflict", "include", "exclude", "all"],
  ft: ["todo", "mine_include", "mine_maybe", "mine_exclude", "conflict", "include", "exclude", "all"],
};

export function ScreeningWorkbench({ stage }: { stage: Stage }) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const { review, refresh } = useReview();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const rid = review.id;
  const [view, setView] = useState("todo");
  const [search, setSearch] = useState("");
  const [current, setCurrent] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [labels, setLabels] = useState("");
  const openedAt = useRef<number>(Date.now());
  const onError = (e: unknown) => toast.error(e instanceof ApiError && e.status === 402 ? t("aiNeedKey") : e instanceof ApiError ? e.message : c("error"));

  const qs = new URLSearchParams({ stage, view, search, limit: "200" }).toString();
  const page = useQuery<RecordPage>({ queryKey: ["records", rid, stage, view, search], queryFn: () => api.get(`/reviews/${rid}/records?${qs}`) });
  const kw = useQuery<KeywordCounts>({ queryKey: ["keywords", rid], queryFn: () => api.get(`/reviews/${rid}/keywords`) });
  const items = useMemo(() => page.data?.items ?? [], [page.data]);
  const index = Math.max(0, items.findIndex((r) => r.id === current));
  const rec: StudyRecord | undefined = items[index] ?? items[0];

  useEffect(() => {
    if (items.length && (current === null || !items.some((r) => r.id === current))) setCurrent(items[0].id);
  }, [items, current]);
  useEffect(() => {
    openedAt.current = Date.now();
    setReason(rec?.my_decision?.reason ?? rec?.ai?.reason ?? "");
    setNote(rec?.my_decision?.note ?? "");
    setLabels(rec?.labels ?? "");
  }, [rec?.id, rec?.my_decision, rec?.ai, rec?.labels]);

  const stageStats = review.counts.stages[stage];
  const required = review.counts.required_reviewers;
  const editable = canReview(review.my_role);
  const admin = canEdit(review.my_role);

  const goto = useCallback((delta: number) => {
    if (!items.length) return;
    const i = Math.min(items.length - 1, Math.max(0, index + delta));
    setCurrent(items[i].id);
  }, [items, index]);

  const decide = useMutation({
    mutationFn: ({ id, decision, consensus }: { id: number; decision: string; consensus?: boolean }) =>
      api.post<StudyRecord>(`/reviews/${rid}/records/${id}/decision`, {
        stage, decision, reason: decision === "exclude" ? reason : "", note,
        seconds: Math.min(3600, (Date.now() - openedAt.current) / 1000), as_consensus: !!consensus,
      }),
    onSuccess: (_r, vars) => {
      if (labels !== (rec?.labels ?? "")) api.patch(`/reviews/${rid}/records/${vars.id}`, { labels }).catch(() => undefined);
      const next = items[index + 1]?.id ?? items[index - 1]?.id ?? null;
      if (view === "todo" || view === "conflict") setCurrent(next);
      qc.invalidateQueries({ queryKey: ["records", rid] });
      refresh();
    },
    onError,
  });
  const clear = useMutation({ mutationFn: (id: number) => api.delete(`/reviews/${rid}/records/${id}/decision?stage=${stage}`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["records", rid] }); refresh(); }, onError });
  const aiRun = useMutation({
    mutationFn: () => api.post<Job>(`/reviews/${rid}/ai/screen`, { stage, limit: 50 }),
    onSuccess: (job) => { toast.success(t("aiDone", { ok: Number((job.result as { ok?: number }).ok ?? 0) })); qc.invalidateQueries({ queryKey: ["records", rid] }); },
    onError,
  });
  const pdfUpload = useMutation({
    mutationFn: async ({ id, file }: { id: number; file: File }) => { const f = new FormData(); f.append("file", file); return api.upload<StudyRecord>(`/reviews/${rid}/records/${id}/pdf`, f); },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["records", rid] }), onError,
  });
  const pdfFetch = useMutation({ mutationFn: (id: number) => api.post<StudyRecord>(`/reviews/${rid}/records/${id}/pdf/fetch`), onSuccess: () => qc.invalidateQueries({ queryKey: ["records", rid] }), onError });
  const notRetrieved = useMutation({ mutationFn: (id: number) => api.post<StudyRecord>(`/reviews/${rid}/records/${id}/pdf/not-retrieved`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["records", rid] }); refresh(); }, onError });

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || e.metaKey || e.ctrlKey || !rec || !editable) return;
      const k = e.key.toLowerCase();
      if (k === "i") decide.mutate({ id: rec.id, decision: "include" });
      else if (k === "m") decide.mutate({ id: rec.id, decision: "maybe" });
      else if (k === "e") decide.mutate({ id: rec.id, decision: "exclude" });
      else if (e.key === "ArrowRight" || k === "j") goto(1);
      else if (e.key === "ArrowLeft" || k === "k") goto(-1);
      else if (k === "p" && rec.has_pdf) window.open(api.url(`/reviews/${rid}/records/${rec.id}/pdf`), "_blank");
      else return;
      e.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rec, editable, decide, goto, rid]);

  const inc = review.criteria.highlight_include;
  const exc = review.criteria.highlight_exclude;
  const fileInput = useRef<HTMLInputElement>(null);

  return (
    <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)_240px]">
      {/* Queue */}
      <aside className="flex max-h-[calc(100vh-14rem)] flex-col rounded-xl border border-border bg-card">
        <div className="space-y-2 border-b border-border p-3">
          <Select value={view} onValueChange={(v: string) => { setView(v); setCurrent(null); }}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{VIEWS[stage].map((v) => <SelectItem key={v} value={v}>{t(`views.${v}`)}</SelectItem>)}</SelectContent>
          </Select>
          <div className="relative"><Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><Input className="pl-8" placeholder={t("search")} value={search} onChange={(e) => { setSearch(e.target.value); setCurrent(null); }} /></div>
          <div>
            <Progress value={stageStats.pool ? Math.round((stageStats.my_done / stageStats.pool) * 100) : 0} />
            <p className="mt-1 text-xs text-muted-foreground">{t("progress", { done: stageStats.my_done, total: stageStats.pool })}{stageStats.my_seconds ? ` · ${formatDuration(stageStats.my_seconds)}` : ""}</p>
          </div>
        </div>
        <ol className="scrollbar-thin flex-1 overflow-y-auto p-1.5">
          {items.map((r, i) => (
            <li key={r.id}>
              <button onClick={() => setCurrent(r.id)} className={cn("w-full rounded-lg px-2.5 py-2 text-left transition-colors", r.id === rec?.id ? "bg-brand-50 dark:bg-brand-950" : "hover:bg-muted")}>
                <p className="line-clamp-2 text-xs font-medium leading-snug">{r.title || "(untitled)"}</p>
                <p className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span>{i + 1}</span>{r.year && <span>· {r.year}</span>}
                  {r.my_decision && <span className={cn("ml-auto size-2 rounded-full", r.my_decision.decision === "include" && "bg-include", r.my_decision.decision === "maybe" && "bg-maybe", r.my_decision.decision === "exclude" && "bg-exclude")} />}
                  {r.has_pdf && <FileText className="size-3" />}
                </p>
              </button>
            </li>
          ))}
          {page.isLoading && <li className="p-3 text-xs text-muted-foreground">{c("loading")}</li>}
          {!page.isLoading && !items.length && <li className="p-3 text-xs text-muted-foreground">{view === "todo" ? t("allDone") : t("empty")}</li>}
        </ol>
        <div className="flex items-center justify-between border-t border-border p-2 text-xs text-muted-foreground">
          <Button size="xs" variant="ghost" onClick={() => goto(-1)} disabled={index <= 0}><ChevronLeft />{c("previous")}</Button>
          <span>{items.length ? `${index + 1} / ${page.data?.total ?? items.length}` : "0"}</span>
          <Button size="xs" variant="ghost" onClick={() => goto(1)} disabled={index >= items.length - 1}>{c("next")}<ChevronRight /></Button>
        </div>
      </aside>

      {/* Reading pane */}
      <section className="min-w-0">
        {!rec ? (
          <EmptyState icon={<Sparkles />} title={view === "todo" ? t("allDone") : t("empty")} />
        ) : (
          <article className="rounded-xl border border-border bg-card shadow-card">
            <div className="p-6">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                {rec.year && <Badge variant="brand">{rec.year}</Badge>}
                {rec.journal && <Badge variant="secondary">{rec.journal}</Badge>}
                {rec.source_db && <Badge variant="secondary">{rec.source_db}</Badge>}
                <StatusBadge status={stage === "ta" ? rec.ta_status : rec.ft_status} label={c(`decision.${stage === "ta" ? rec.ta_status : rec.ft_status}` as "decision.pending")} />
                {rec.doi && <a className="ml-auto inline-flex items-center gap-1 text-primary hover:underline" href={`https://doi.org/${rec.doi}`} target="_blank" rel="noreferrer">doi:{rec.doi}<ExternalLink className="size-3" /></a>}
              </div>
              <h2 className="font-display mt-3 text-2xl font-semibold leading-snug"><Highlight text={rec.title} include={inc} exclude={exc} /></h2>
              <p className="mt-1 text-sm text-muted-foreground">{rec.authors}</p>
              <div className="mt-5 text-[15px] leading-relaxed">
                {rec.abstract ? <Highlight text={rec.abstract} include={inc} exclude={exc} /> : <span className="italic text-muted-foreground">{t("noAbstract")}</span>}
              </div>
              {rec.keywords && <p className="mt-4 text-xs text-muted-foreground"><span className="font-medium">{t("keywords")}:</span> {rec.keywords}</p>}
              {rec.ai && (
                <div className="mt-5 flex items-start gap-3 rounded-lg border border-conflict/20 bg-conflict-bg/60 p-3 text-sm">
                  <Bot className="mt-0.5 size-4 shrink-0 text-conflict" />
                  <div className="min-w-0">
                    <p><span className="font-medium text-conflict">{t("aiSuggests")}</span> <b>{c(`decision.${rec.ai.decision}` as "decision.include")}</b> <span className="text-muted-foreground">({Math.round(rec.ai.confidence * 100)}%)</span>{rec.ai.reason && <span className="text-muted-foreground"> · {rec.ai.reason}</span>}</p>
                    <p className="mt-0.5 text-muted-foreground">{rec.ai.rationale}</p>
                  </div>
                  {editable && !rec.my_decision && <Button size="xs" variant="outline" className="ml-auto shrink-0" onClick={() => { setReason(rec.ai?.reason ?? ""); decide.mutate({ id: rec.id, decision: rec.ai!.decision }); }}>{t("acceptAi")}</Button>}
                </div>
              )}
              {(rec.decisions.length > 0 || (required > 1 && review.settings.blind && !admin)) && (
                <div className="mt-4 space-y-1 text-xs text-muted-foreground">
                  {rec.decisions.map((d) => (
                    <p key={d.reviewer}><span className="font-medium text-foreground">{d.reviewer === me?.id ? t("yourDecision") : d.name}</span>: {c(`decision.${d.decision}` as "decision.include")}{d.reason && ` · ${d.reason}`}{d.note && ` · “${d.note}”`}</p>
                  ))}
                  {review.settings.blind && !admin && required > 1 && <p className="italic">{t("others")}: {t("blindHidden")}</p>}
                </div>
              )}
            </div>

            {stage === "ft" && (
              <div className="border-t border-border bg-muted/30 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{t("fullText")}</span>
                  {rec.has_pdf ? (
                    <Button size="sm" variant="outline" asChild><a href={api.url(`/reviews/${rid}/records/${rec.id}/pdf`)} target="_blank" rel="noreferrer"><FileText />{t("openPdf")}</a></Button>
                  ) : (
                    <>
                      <input ref={fileInput} type="file" accept="application/pdf" className="hidden" onChange={(e) => e.target.files?.[0] && pdfUpload.mutate({ id: rec.id, file: e.target.files[0] })} />
                      <Button size="sm" variant="outline" onClick={() => fileInput.current?.click()} disabled={pdfUpload.isPending}><Upload />{t("uploadPdf")}</Button>
                      {rec.doi && <Button size="sm" variant="outline" onClick={() => pdfFetch.mutate(rec.id)} disabled={pdfFetch.isPending}><Search />{t("fetchPdf")}</Button>}
                      <Button size="sm" variant={rec.pdf_status === "not_retrieved" ? "secondary" : "ghost"} onClick={() => notRetrieved.mutate(rec.id)}><XCircle />{rec.pdf_status === "not_retrieved" ? t("notRetrievedOn") : t("notRetrieved")}</Button>
                    </>
                  )}
                </div>
                {rec.has_pdf && <iframe title="pdf" src={api.url(`/reviews/${rid}/records/${rec.id}/pdf`)} className="mt-3 h-[620px] w-full rounded-lg border border-border bg-white" />}
                {!rec.has_pdf && rec.pdf_status !== "not_retrieved" && <p className="mt-2 text-xs text-muted-foreground">{t("noPdf")}</p>}
              </div>
            )}

            {editable && (
              <div className="space-y-3 border-t border-border p-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <Select value={reason} onValueChange={setReason}>
                    <SelectTrigger><SelectValue placeholder={t("reason")} /></SelectTrigger>
                    <SelectContent>{review.criteria.exclusion_reasons.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                  </Select>
                  <div className="relative"><Tag className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><Input className="pl-8" placeholder={`${t("labels")} (${t("labelsHint")})`} value={labels} onChange={(e) => setLabels(e.target.value)} /></div>
                  <Textarea className="min-h-9 md:h-9" placeholder={t("addNote")} value={note} onChange={(e) => setNote(e.target.value)} />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="include" onClick={() => decide.mutate({ id: rec.id, decision: "include" })} disabled={decide.isPending}>{c("decision.include")}<Kbd>I</Kbd></Button>
                  <Button variant="maybe" onClick={() => decide.mutate({ id: rec.id, decision: "maybe" })} disabled={decide.isPending}>{c("decision.maybe")}<Kbd>M</Kbd></Button>
                  <Button variant="exclude" onClick={() => decide.mutate({ id: rec.id, decision: "exclude" })} disabled={decide.isPending}>{c("decision.exclude")}<Kbd>E</Kbd></Button>
                  {rec.my_decision && <Button variant="ghost" size="sm" onClick={() => clear.mutate(rec.id)}>{t("clearDecision")}</Button>}
                  {admin && (stage === "ta" ? rec.ta_status : rec.ft_status) === "conflict" && (
                    <div className="ml-auto flex items-center gap-1 text-xs"><span className="text-muted-foreground">{t("consensus")}:</span>
                      {["include", "maybe", "exclude"].map((d) => <Button key={d} size="xs" variant="outline" onClick={() => decide.mutate({ id: rec.id, decision: d, consensus: true })}>{c(`decision.${d}` as "decision.include")}</Button>)}
                    </div>
                  )}
                </div>
              </div>
            )}
          </article>
        )}
      </section>

      {/* Rail */}
      <aside className="space-y-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("shortcuts")}</p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{t("shortcutList")}</p>
        </div>
        {editable && <AiCard review={review} onRun={() => aiRun.mutate()} running={aiRun.isPending} label={t("runAi")} />}
        <KeywordsCard review={review} counts={kw.data} editable={admin} onPick={(k) => { setSearch(k); setCurrent(null); }} onChanged={refresh} />
        <div className="rounded-xl border border-border bg-card p-4 text-xs">
          <p className="font-semibold uppercase tracking-wide text-muted-foreground">{c("decision.conflict")}</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-conflict">{stageStats.conflict}</p>
          <Tooltip><TooltipTrigger asChild><p className="mt-1 text-muted-foreground">{required} reviewer(s) / record</p></TooltipTrigger><TooltipContent>{review.settings.blind ? "Blind mode on" : "Blind mode off"}</TooltipContent></Tooltip>
        </div>
      </aside>
    </div>
  );
}
