"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUpDown, Bot, ChevronLeft, ChevronRight, ExternalLink, FileText, Lightbulb, Search, Sparkles, Tag, Upload, X, XCircle } from "lucide-react";
import { api, ApiError, type ImportRow, type Job, type KeywordCounts, type LabelCount, type StudyRecord, type RecordPage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { cn, formatDuration } from "@/lib/utils";
import { canEdit, canReview, useReview } from "@/components/app/review-context";
import { Highlight } from "@/components/app/highlight";
import { AiCard, AiRunSummary, aiErrorKind, DEFAULT_PROVIDER, type AiRunResult } from "@/components/app/ai-card";
import { JobProgress } from "@/components/app/job-progress";
import { isLive, useJob } from "@/lib/use-job";
import { KeywordsCard } from "@/components/app/keywords-card";
import { LearnedCard } from "@/components/app/learned-card";
import { SearchCriteriaCard } from "@/components/app/search-criteria-card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MultiSelect } from "@/components/ui/multi-select";
import { EmptyState, Kbd, Progress } from "@/components/ui/misc";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type Stage = "ta" | "ft";
const VIEWS: { [k in Stage]: string[] } = {
  ta: ["todo", "mine_include", "mine_maybe", "mine_exclude", "conflict", "include", "exclude", "all"],
  ft: ["todo", "mine_include", "mine_maybe", "mine_exclude", "conflict", "include", "exclude", "no_pdf", "not_retrieved", "all"],
};
// Orders of the queue (GET /records?sort=...); "import" is the order of the imported files.
// Title/abstract screening also follows your suggestions learned from your decisions (D-54).
const BASE_SORTS = ["import", "title", "title_desc", "year_desc", "year", "author", "journal", "ai", "ai_exclude"];
const SORTS: { [k in Stage]: string[] } = { ta: [...BASE_SORTS, "learned", "learned_exclude"], ft: BASE_SORTS };
// The "No reason" choice of the exclusion reason (a select item cannot have an empty value).
const NO_REASON = "__none__";
// The queue is read this many records at a time (GET /records?offset=...).
const PAGE = 200;
// How many records an AI run takes (D-40, D-43): any number from the record on screen, at most
// AI_ALL (AI_MAX_RUN in the API). A full text is a long prompt, so a full-text run starts at
// one record. A run bigger than AI_CONFIRM asks first, as each record is a call billed to the
// key used.
const AI_DEFAULT_COUNT: { [k in Stage]: number } = { ta: 50, ft: 1 };
const AI_ALL = 20000;
const AI_CONFIRM = 500;

export function ScreeningWorkbench({ stage }: { stage: Stage }) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const { review, refresh } = useReview();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const rid = review.id;
  // Views, files and labels can be picked several at once (none: no filter); a record shows
  // when it matches any view, any file and any label picked.
  const [views, setViews] = useState<string[]>(["todo"]);
  const [search, setSearch] = useState("");
  const [fileIds, setFileIds] = useState<string[]>([]);
  const [labelFilter, setLabelFilter] = useState<string[]>([]);
  const [sort, setSort] = useState("import");
  // Keywords clicked in the rail: the queue shows the records that mention all of them (or any).
  const [kwFilter, setKwFilter] = useState<string[]>([]);
  const [kwMode, setKwMode] = useState<"all" | "any">("all");
  const [current, setCurrent] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [labels, setLabels] = useState("");
  const [aiCount, setAiCount] = useState(String(AI_DEFAULT_COUNT[stage]));
  const [aiRedo, setAiRedo] = useState(false);
  // The queue is read PAGE records at a time, from the first page again whenever the list
  // changes; `last` lands on the last record of the page reached (going back with Previous).
  const listKey = JSON.stringify([views, search, fileIds, labelFilter, sort, kwFilter, kwMode]);
  const [paging, setPaging] = useState({ key: "", offset: 0, last: false });
  const offset = paging.key === listKey ? paging.offset : 0;
  const landOnLast = paging.key === listKey && paging.last;
  const openedAt = useRef<number>(Date.now());
  const onError = (e: unknown) => toast.error(e instanceof ApiError && e.status === 402 ? t("aiNeedKey") : e instanceof ApiError ? e.message : c("error"));

  const params = new URLSearchParams({
    stage, search, limit: String(PAGE),
    ...(offset ? { offset: String(offset) } : {}),
    ...(sort !== "import" ? { sort } : {}),
  });
  const viewList = views.length ? views : ["all"];
  viewList.forEach((v) => params.append("view", v));
  fileIds.forEach((f) => params.append("import_id", f));
  labelFilter.forEach((l) => params.append("label", l));
  kwFilter.forEach((k) => params.append("kw", k));
  if (kwFilter.length > 1) params.set("kw_mode", kwMode);
  const qs = params.toString();
  // The list on screen stays (dimmed) while the next one loads.
  const page = useQuery<RecordPage>({ queryKey: ["records", rid, stage, views, search, fileIds, labelFilter, kwFilter, kwMode, sort, offset], queryFn: () => api.get(`/reviews/${rid}/records?${qs}`), placeholderData: keepPreviousData });
  const samekw = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();
  const togglePick = (k: string) => {
    setKwFilter((f) => (f.some((x) => samekw(x, k)) ? f.filter((x) => !samekw(x, k)) : [...f, k]));
    setCurrent(null);
  };
  const showAll = () => { setKwFilter([]); setSearch(""); setCurrent(null); };
  // A search's own keywords and criteria are edited with its file alone in the list.
  const oneFile = fileIds.length === 1 ? fileIds[0] : "";
  const onlyTodo = views.length === 1 && views[0] === "todo";
  // Whether a record decided or flagged here leaves the list: every view picked drops it.
  const leavesList = (dropping: string[]) => views.length > 0 && views.every((v) => dropping.includes(v));
  const imports = useQuery<ImportRow[]>({ queryKey: ["imports", rid], queryFn: () => api.get(`/reviews/${rid}/imports`) });
  const labelList = useQuery<LabelCount[]>({ queryKey: ["labels", rid], queryFn: () => api.get(`/reviews/${rid}/labels`) });
  const kw = useQuery<KeywordCounts>({
    queryKey: ["keywords", rid, oneFile],
    queryFn: () => api.get(`/reviews/${rid}/keywords${oneFile ? `?import_id=${oneFile}` : ""}`),
  });
  const items = useMemo(() => page.data?.items ?? [], [page.data]);
  const total = page.data?.total ?? 0;
  const index = Math.max(0, items.findIndex((r) => r.id === current));
  const rec: StudyRecord | undefined = items[index] ?? items[0];
  const pageTo = useCallback((o: number, last = false) => { setPaging({ key: listKey, offset: o, last }); setCurrent(null); }, [listKey]);

  useEffect(() => {
    if (page.isPlaceholderData || !page.data) return;
    if (!items.length) {                     // a page emptied by decisions: back to the one before
      if (offset > 0) setPaging({ key: listKey, offset: Math.max(0, offset - PAGE), last: false });
      return;
    }
    if (current === null || !items.some((r) => r.id === current)) {
      setCurrent(landOnLast ? items[items.length - 1].id : items[0].id);
      if (landOnLast) setPaging((p) => ({ ...p, last: false }));
    }
  }, [items, current, landOnLast, offset, listKey, page.isPlaceholderData, page.data]);
  useEffect(() => {
    openedAt.current = Date.now();
    setNote(rec?.my_decision?.note ?? "");
    setLabels(rec?.labels ?? "");
  }, [rec?.id, rec?.my_decision, rec?.labels]);
  // The exclusion reason starts from your decision, else from the AI's suggestion, else from
  // the one learned from your decisions, also when a suggestion arrives while the record is
  // open (without touching the note or the timer).
  useEffect(() => {
    const learnedReason = rec?.learned && rec.learned.decision === "exclude" ? rec.learned.reason : "";
    setReason(rec?.my_decision?.reason ?? (rec?.ai?.reason || learnedReason || ""));
  }, [rec?.id, rec?.my_decision, rec?.ai, rec?.learned]);

  const stageStats = review.counts.stages[stage];
  const required = review.counts.required_reviewers;
  const editable = canReview(review.my_role);
  const admin = canEdit(review.my_role);

  // Next and Previous go on to the next or previous page at the ends of the one loaded.
  const goto = useCallback((delta: number) => {
    if (!items.length) return;
    const i = index + delta;
    if (i >= items.length && offset + items.length < total) pageTo(offset + PAGE);
    else if (i < 0 && offset > 0) pageTo(Math.max(0, offset - PAGE), true);
    else setCurrent(items[Math.min(items.length - 1, Math.max(0, i))].id);
  }, [items, index, offset, total, pageTo]);

  const decide = useMutation({
    mutationFn: ({ id, decision, consensus }: { id: number; decision: string; consensus?: boolean }) =>
      api.post<StudyRecord>(`/reviews/${rid}/records/${id}/decision`, {
        stage, decision, reason: decision === "exclude" ? reason : "", note,
        seconds: Math.min(3600, (Date.now() - openedAt.current) / 1000), as_consensus: !!consensus,
      }),
    onSuccess: (_r, vars) => {
      if (labels !== (rec?.labels ?? "")) api.patch(`/reviews/${rid}/records/${vars.id}`, { labels }).then(() => qc.invalidateQueries({ queryKey: ["labels", rid] })).catch(() => undefined);
      const next = items[index + 1]?.id ?? items[index - 1]?.id ?? null;
      if (leavesList(["todo", "conflict"])) setCurrent(next);
      qc.invalidateQueries({ queryKey: ["records", rid] });
      refresh();
    },
    onError,
  });
  const clear = useMutation({ mutationFn: (id: number) => api.delete(`/reviews/${rid}/records/${id}/decision?stage=${stage}`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["records", rid] }); refresh(); }, onError });
  // AI suggestions run in the background. Each one shows as soon as it is saved (below); the
  // end of the run is announced here, and how it went stays in the AI panel.
  const aiJob = useJob(rid, ["ai_screen"], (job) => {
    const r = job.result as AiRunResult;
    const ok = Number(r.ok ?? 0);
    const kind = aiErrorKind(job);
    if (job.status === "failed") toast.error(t("aiFailed"), { description: job.error });
    else if (!kind && r.total === 0) toast.info(t("aiNothing"));
    else if (!kind) toast.success(t("aiDone", { ok }));
    else if (ok > 0) toast.warning(t("aiPartial", { ok, failed: Number(r.failed ?? 0) }), { description: t("aiSeePanel") });
    else toast.error(t("aiNone"), { description: t("aiSeePanel") });
    qc.invalidateQueries({ queryKey: ["records", rid] });
  });
  // The AI follows the list as shown (views, files, labels, keywords, search and order), from the
  // record on screen round to the top, and takes the records without your decision and (unless
  // redone) without a suggestion, as many as typed (1 = the record on screen, if it has neither).
  // The server reads them from the whole list, not only from the page loaded here (D-40).
  const aiLimit = Math.min(AI_ALL, Math.max(1, Math.floor(Number(aiCount)) || 1));
  const aiList = {
    stage, redo: aiRedo,
    queue: { view: viewList, search, sort, label: labelFilter, import_id: fileIds, kw: kwFilter, kw_mode: kwMode },
  };
  const aiRun = useMutation({
    mutationFn: () => api.post<Job>(`/reviews/${rid}/ai/screen`, { ...aiList, limit: aiLimit, start_id: rec?.id ?? null }),
    onSuccess: aiJob.follow,
    onError,
  });
  const aiRunning = aiRun.isPending || aiJob.running;
  // How many records of the list a run can take; asked again whenever the list or the
  // decisions change (its key starts like the list's), but not while a run goes on, nor at
  // each digit typed in the number (the next run takes the smaller of the two).
  const aiPreview = useQuery<{ available: number; next: number; no_pdf?: number }>({
    queryKey: ["records", rid, "ai-preview", JSON.stringify(aiList)],
    queryFn: () => api.post(`/reviews/${rid}/ai/screen/preview`, { ...aiList, limit: AI_ALL }),
    enabled: editable && !aiRunning,
  });
  const aiAvailable = aiPreview.data?.available ?? 0;
  const aiNext = Math.min(aiAvailable, aiLimit);
  // In full-text screening the records without a PDF are left out (D-44), and the panel says so.
  const aiNoPdf = aiPreview.data?.no_pdf ? t("aiNoPdf", { n: aiPreview.data.no_pdf }) : "";
  const aiNothing = aiNoPdf || t(aiRedo ? "aiNothingRedo" : "aiNothing");
  const runAi = () => {
    if (!aiNext) toast.info(aiNothing);
    else if (aiNext <= AI_CONFIRM || window.confirm(t("aiConfirm", { n: aiNext }))) aiRun.mutate();
  };
  const aiHint = !aiPreview.data ? undefined
    : aiAvailable ? [t(aiRedo ? "aiScopeRedo" : "aiScope", { n: aiAvailable, k: aiNext }), aiNoPdf].filter(Boolean).join(" ")
    : aiNothing;
  // While a run goes on, the queue is fetched again each time it saves one more suggestion
  // (a fetch already under way is let finish rather than restarted).
  const aiProgress = (aiJob.job?.result ?? {}) as AiRunResult;
  const aiSaved = Number(aiProgress.ok ?? 0);
  useEffect(() => {
    if (aiSaved > 0) qc.invalidateQueries({ queryKey: ["records", rid] }, { cancelRefetch: false });
  }, [aiSaved, qc, rid]);
  // How your last run on this stage went (runs from before the stage was recorded count for both).
  const lastAiRun = aiJob.jobs.find((j) => j.kind === "ai_screen" && !isLive(j) && !!me && j.user_id === me.id
    && ((j.result as { stage?: string }).stage ?? stage) === stage);
  // A new PDF changes the viewer's address, so the browser shows it instead of the old one.
  const [pdfVersion, setPdfVersion] = useState(0);
  const pdfChanged = () => { setPdfVersion((v) => v + 1); qc.invalidateQueries({ queryKey: ["records", rid] }); };
  const pdfUpload = useMutation({
    mutationFn: async ({ id, file }: { id: number; file: File }) => { const f = new FormData(); f.append("file", file); return api.upload<StudyRecord>(`/reviews/${rid}/records/${id}/pdf`, f); },
    onSuccess: pdfChanged, onError,
  });
  const pdfFetch = useMutation({ mutationFn: (id: number) => api.post<StudyRecord>(`/reviews/${rid}/records/${id}/pdf/fetch`), onSuccess: pdfChanged, onError });
  const pdfRemove = useMutation({ mutationFn: (id: number) => api.delete<StudyRecord>(`/reviews/${rid}/records/${id}/pdf`), onSuccess: () => { pdfChanged(); refresh(); }, onError });
  // Flagged not retrievable, a report leaves "To screen" and "No PDF" (D-46): go on to the next.
  const notRetrieved = useMutation({
    mutationFn: (id: number) => api.post<StudyRecord>(`/reviews/${rid}/records/${id}/pdf/not-retrieved`),
    onSuccess: (r) => {
      if (r.pdf_status === "not_retrieved" && leavesList(["todo", "no_pdf"])) setCurrent(items[index + 1]?.id ?? items[index - 1]?.id ?? null);
      qc.invalidateQueries({ queryKey: ["records", rid] });
      refresh();
    },
    onError,
  });

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

  // The review's keywords, plus those of every search (imported file) that found this record.
  const ownSets = (rec?.found_in ?? []).map((i) => review.criteria.search_keywords?.[i]).filter((x) => !!x);
  const inc = Array.from(new Set([...review.criteria.highlight_include, ...ownSets.flatMap((x) => x.include)]));
  const exc = Array.from(new Set([...review.criteria.highlight_exclude, ...ownSets.flatMap((x) => x.exclude)]));
  const fileLabel = imports.data?.find((i) => i.id === oneFile)?.filename;
  const fileInput = useRef<HTMLInputElement>(null);

  return (
    <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)_240px] 2xl:grid-cols-[320px_minmax(0,1fr)_280px]">
      {/* Queue */}
      <aside className="flex max-h-[calc(100vh-14rem)] flex-col rounded-xl border border-border bg-card">
        <div className="space-y-2 border-b border-border p-3">
          <MultiSelect ariaLabel={t("viewFilter")} allLabel={t("views.all")} value={views}
                       options={VIEWS[stage].filter((v) => v !== "all").map((v) => ({ value: v, label: t(`views.${v}`) }))}
                       onChange={(v) => { setViews(v); setCurrent(null); }} />
          {(imports.data?.length ?? 0) > 1 && (
            <MultiSelect ariaLabel={t("fileFilter")} allLabel={t("allFiles")} value={fileIds}
                         options={imports.data!.map((i) => ({ value: i.id, label: `${i.filename}${i.source_db ? ` · ${i.source_db}` : ""}` }))}
                         onChange={(v) => { setFileIds(v); setCurrent(null); }} />
          )}
          {!!labelList.data?.length && (
            <MultiSelect ariaLabel={t("labelFilter")} allLabel={t("allLabels")} value={labelFilter}
                         options={labelList.data.map((l) => ({ value: l.label, label: `${l.label} (${l.n})` }))}
                         onChange={(v) => { setLabelFilter(v); setCurrent(null); }} />
          )}
          <Select value={sort} onValueChange={(v: string) => { setSort(v); setCurrent(null); }}>
            <SelectTrigger aria-label={t("sortLabel")} title={t("sortLabel")} className="justify-start gap-2">
              <ArrowUpDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden /><SelectValue className="flex-1 text-left" />
            </SelectTrigger>
            <SelectContent>{SORTS[stage].map((s) => <SelectItem key={s} value={s}>{t(`sort.${s}`)}</SelectItem>)}</SelectContent>
          </Select>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input className="px-8" placeholder={t("search")} value={search} onChange={(e) => { setSearch(e.target.value); setCurrent(null); }} />
            {search && (
              <button type="button" aria-label={t("clearSearch")} title={t("clearSearch")} onClick={() => { setSearch(""); setCurrent(null); }}
                      className="absolute right-1.5 top-1.5 inline-flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
                <X className="size-3.5" />
              </button>
            )}
          </div>
          {!!kwFilter.length && (
            <div className="rounded-lg border border-border bg-muted/40 p-2 text-xs">
              <p className="text-[11px] text-muted-foreground">{t("kwFilterTitle")}</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {kwFilter.map((k) => (
                  <li key={k} className="inline-flex max-w-full items-center gap-1 rounded-md bg-brand-50 pl-1.5 text-brand-800 dark:bg-brand-950 dark:text-brand-200">
                    <span className="truncate">{k}</span>
                    <button type="button" aria-label={t("kwRemove", { keyword: k })} title={t("kwRemove", { keyword: k })} onClick={() => togglePick(k)}
                            className="rounded-r-md px-1 py-0.5 hover:bg-black/10"><X className="size-3" /></button>
                  </li>
                ))}
              </ul>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                {kwFilter.length > 1 ? (
                  <div role="group" aria-label={t("kwModeLabel")} className="inline-flex rounded-md border border-border bg-background p-0.5">
                    {(["all", "any"] as const).map((m) => (
                      <button key={m} type="button" aria-pressed={kwMode === m} onClick={() => { setKwMode(m); setCurrent(null); }}
                              className={cn("rounded px-2 py-0.5", kwMode === m ? "bg-brand-600 text-white" : "text-muted-foreground hover:text-foreground")}>
                        {t(m === "all" ? "kwModeAll" : "kwModeAny")}
                      </button>
                    ))}
                  </div>
                ) : <span className="text-muted-foreground">{t("kwFilterMore")}</span>}
                <button type="button" onClick={showAll} className="font-medium text-primary underline-offset-4 hover:underline">{t("showAll")}</button>
              </div>
            </div>
          )}
          <div>
            <Progress value={stageStats.pool ? Math.round((stageStats.my_done / stageStats.pool) * 100) : 0} />
            <p className="mt-1 text-xs text-muted-foreground">{t("progress", { done: stageStats.my_done, total: stageStats.pool })}{stageStats.my_seconds ? ` · ${formatDuration(stageStats.my_seconds)}` : ""}{stageStats.not_retrieved ? ` · ${t("progressNotRetrieved", { n: stageStats.not_retrieved })}` : ""}</p>
          </div>
        </div>
        <ol className={cn("scrollbar-thin flex-1 overflow-y-auto p-1.5 transition-opacity", page.isPlaceholderData && "opacity-60")}>
          {offset > 0 && (
            <li><button type="button" onClick={() => pageTo(Math.max(0, offset - PAGE), true)} className="w-full rounded-lg px-2.5 py-1.5 text-left text-[11px] font-medium text-primary hover:bg-muted">{t("pagePrev", { n: Math.min(PAGE, offset) })}</button></li>
          )}
          {items.map((r, i) => (
            <li key={r.id}>
              <button onClick={() => setCurrent(r.id)} className={cn("w-full rounded-lg px-2.5 py-2 text-left transition-colors", r.id === rec?.id ? "bg-brand-50 dark:bg-brand-950" : "hover:bg-muted")}>
                <p className="line-clamp-2 text-xs font-medium leading-snug">{r.title || "(untitled)"}</p>
                <p className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span>{offset + i + 1}</span>{r.year && <span>· {r.year}</span>}
                  {r.ai && (
                    <span title={t("aiListMark", { decision: c(`decision.${r.ai.decision}` as "decision.include") })}
                          className={cn("inline-flex", r.ai.decision === "include" && "text-include", r.ai.decision === "maybe" && "text-maybe", r.ai.decision === "exclude" && "text-exclude")}>
                      <Bot className="size-3" aria-hidden /><span className="sr-only">{t("aiListMark", { decision: c(`decision.${r.ai.decision}` as "decision.include") })}</span>
                    </span>
                  )}
                  {r.learned && !r.my_decision && (
                    <span title={t("learnedListMark", { decision: c(`decision.${r.learned.decision}` as "decision.include") })}
                          className={cn("inline-flex", r.learned.decision === "include" && "text-include", r.learned.decision === "maybe" && "text-maybe", r.learned.decision === "exclude" && "text-exclude")}>
                      <Lightbulb className="size-3" aria-hidden /><span className="sr-only">{t("learnedListMark", { decision: c(`decision.${r.learned.decision}` as "decision.include") })}</span>
                    </span>
                  )}
                  {r.my_decision && <span className={cn("ml-auto size-2 rounded-full", r.my_decision.decision === "include" && "bg-include", r.my_decision.decision === "maybe" && "bg-maybe", r.my_decision.decision === "exclude" && "bg-exclude")} />}
                  {r.has_pdf && <FileText className="size-3" />}
                </p>
              </button>
            </li>
          ))}
          {offset + items.length < total && (
            <li><button type="button" onClick={() => pageTo(offset + PAGE)} className="w-full rounded-lg px-2.5 py-1.5 text-left text-[11px] font-medium text-primary hover:bg-muted">{t("pageNext", { n: Math.min(PAGE, total - offset - items.length) })}</button></li>
          )}
          {page.isLoading && <li className="p-3 text-xs text-muted-foreground">{c("loading")}</li>}
          {!page.isLoading && !items.length && <li className="p-3 text-xs text-muted-foreground">{onlyTodo ? t("allDone") : t("empty")}</li>}
        </ol>
        <div className="flex items-center justify-between border-t border-border p-2 text-xs text-muted-foreground">
          <Button size="xs" variant="ghost" onClick={() => goto(-1)} disabled={offset + index <= 0}><ChevronLeft />{c("previous")}</Button>
          <span>{items.length ? `${offset + index + 1} / ${total || items.length}` : "0"}</span>
          <Button size="xs" variant="ghost" onClick={() => goto(1)} disabled={offset + index >= total - 1}>{c("next")}<ChevronRight /></Button>
        </div>
      </aside>

      {/* Reading pane */}
      <section className="min-w-0">
        {!rec ? (
          <EmptyState icon={<Sparkles />} title={onlyTodo ? t("allDone") : t("empty")} />
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
              {/* Your suggestion learned from your own decisions (D-54), beside the AI's. */}
              {rec.learned && (
                <div className={cn("flex items-start gap-3 rounded-lg border border-brand-200 bg-brand-50/60 p-3 text-sm dark:border-brand-900 dark:bg-brand-950/40", rec.ai ? "mt-2" : "mt-5")}>
                  <Lightbulb className="mt-0.5 size-4 shrink-0 text-brand-600" />
                  <p className="min-w-0"><span className="font-medium text-brand-700 dark:text-brand-300">{t("learnedSuggests")}</span> <b>{c(`decision.${rec.learned.decision}` as "decision.include")}</b> <span className="text-muted-foreground">({t("learnedScore", { n: Math.round(rec.learned.score * 100) })})</span>{rec.learned.reason && <span className="text-muted-foreground"> · {rec.learned.reason}</span>}</p>
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
                  <input ref={fileInput} type="file" accept="application/pdf" className="hidden"
                         onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) pdfUpload.mutate({ id: rec.id, file: f }); }} />
                  {rec.has_pdf ? (
                    <>
                      <Button size="sm" variant="outline" asChild><a href={api.url(`/reviews/${rid}/records/${rec.id}/pdf?v=${pdfVersion}`)} target="_blank" rel="noreferrer"><FileText />{t("openPdf")}</a></Button>
                      {editable && <Button size="sm" variant="ghost" onClick={() => fileInput.current?.click()} disabled={pdfUpload.isPending}><Upload />{t("replacePdf")}</Button>}
                      {editable && <Button size="sm" variant="ghost" onClick={() => window.confirm(t("removePdfConfirm")) && pdfRemove.mutate(rec.id)} disabled={pdfRemove.isPending}><XCircle />{t("removePdf")}</Button>}
                    </>
                  ) : (
                    <>
                      <Button size="sm" variant="outline" onClick={() => fileInput.current?.click()} disabled={pdfUpload.isPending}><Upload />{t("uploadPdf")}</Button>
                      {rec.doi && <Button size="sm" variant="outline" onClick={() => pdfFetch.mutate(rec.id)} disabled={pdfFetch.isPending}><Search />{t("fetchPdf")}</Button>}
                      <Button size="sm" variant={rec.pdf_status === "not_retrieved" ? "secondary" : "ghost"} onClick={() => notRetrieved.mutate(rec.id)}><XCircle />{rec.pdf_status === "not_retrieved" ? t("notRetrievedOn") : t("notRetrieved")}</Button>
                    </>
                  )}
                </div>
                {rec.has_pdf && <iframe title="pdf" src={api.url(`/reviews/${rid}/records/${rec.id}/pdf?v=${pdfVersion}`)} className="mt-3 h-[620px] w-full rounded-lg border border-border bg-white" />}
                {!rec.has_pdf && rec.pdf_status !== "not_retrieved" && <p className="mt-2 text-xs text-muted-foreground">{t("noPdf")}</p>}
              </div>
            )}

            {editable && (
              <div className="space-y-3 border-t border-border p-4">
                <div className="grid gap-3 md:grid-cols-3">
                  {/* "No reason" empties the field, so an exclusion can go without one (even when
                      the AI had proposed one). */}
                  <Select value={reason} onValueChange={(v) => setReason(v === NO_REASON ? "" : v)}>
                    <SelectTrigger><SelectValue placeholder={t("reason")} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NO_REASON} className="text-muted-foreground">{t("noReason")}</SelectItem>
                      {review.criteria.exclusion_reasons.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                    </SelectContent>
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
        {/* The criteria of the search the list is filtered on, else of the searches the record
            on screen belongs to (one under the file order, D-42). */}
        <SearchCriteriaCard review={review} importIds={fileIds.length ? fileIds : (rec?.found_in ?? [])}
                            imports={imports.data ?? []} editable={admin} onChanged={refresh} />
        {editable && (
          <AiCard review={review} onRun={runAi} running={aiRunning} label={t("runAi")} hint={aiRunning ? undefined : aiHint}
                  options={(
                    <div className="mt-3 space-y-2">
                      <div className="space-y-1 text-[11px] text-muted-foreground">
                        <label htmlFor="ai-count" className="block">{t("aiBatch")}</label>
                        <div className="flex items-center gap-2">
                          <Input id="ai-count" type="number" inputMode="numeric" min={1} max={AI_ALL} className="h-7 w-20 px-2 text-xs tabular-nums"
                                 value={aiCount} disabled={aiRunning} onChange={(e) => setAiCount(e.target.value)}
                                 onBlur={() => setAiCount(String(aiLimit))} />
                          {aiAvailable > 1 && (
                            <button type="button" className="font-medium text-primary underline-offset-2 hover:underline disabled:opacity-50" disabled={aiRunning}
                                    onClick={() => setAiCount(String(aiAvailable))}>{t("aiBatchAll")}</button>
                          )}
                        </div>
                      </div>
                      <label className="flex items-start gap-2 text-[11px] leading-snug text-muted-foreground">
                        <input type="checkbox" className="mt-0.5 accent-brand-600" checked={aiRedo} disabled={aiRunning} onChange={(e) => setAiRedo(e.target.checked)} />
                        {t("aiRedo")}
                      </label>
                    </div>
                  )}
                  status={aiRunning
                    ? <JobProgress job={aiJob.job} label={aiProgress.total ? t("aiRunningCount", { ok: aiSaved, total: aiProgress.total }) : t("aiRunning")} />
                    : lastAiRun && <AiRunSummary job={lastAiRun} provider={review.settings.ai_provider || DEFAULT_PROVIDER} />} />
        )}
        {editable && stage === "ta" && <LearnedCard reviewId={rid} onReady={() => { setSort("learned"); setCurrent(null); }} />}
        <KeywordsCard review={review} counts={kw.data} editable={admin} picked={kwFilter} onPick={togglePick} onChanged={refresh}
                      search={oneFile && fileLabel ? { importId: oneFile, label: fileLabel } : undefined} />
        <div className="rounded-xl border border-border bg-card p-4 text-xs">
          <p className="font-semibold uppercase tracking-wide text-muted-foreground">{c("decision.conflict")}</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-conflict">{stageStats.conflict}</p>
          <Tooltip><TooltipTrigger asChild><p className="mt-1 text-muted-foreground">{required} reviewer(s) / record</p></TooltipTrigger><TooltipContent>{review.settings.blind ? "Blind mode on" : "Blind mode off"}</TooltipContent></Tooltip>
        </div>
      </aside>
    </div>
  );
}
