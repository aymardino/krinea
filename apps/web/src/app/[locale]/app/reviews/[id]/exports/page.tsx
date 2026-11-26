"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, type ImportRow, type LabelCount } from "@/lib/api";
import { useReview } from "@/components/app/review-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { MultiSelect } from "@/components/ui/multi-select";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/ui/misc";

const STAGES = ["ta", "ft", "extract"] as const;
type Stage = (typeof STAGES)[number];
const STATUSES = ["include", "maybe", "exclude", "conflict", "pending"] as const;
const PDFS = ["available", "missing", "not_retrieved"] as const;
const FORMATS = ["ris", "csv", "xlsx"] as const;
const NO_REASON = "-";      // exclusions given without a reason (NO_REASON in the API's exports.py)

/** A single-choice select of the export form (stage, extraction status). */
function Choice({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>{options.map(([v, text]) => <SelectItem key={v} value={v}>{text}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  );
}

/** A filter that takes several values (D-41), with its label. */
function Filter({ label, all, value, onChange, options }: { label: string; all: string; value: string[]; onChange: (v: string[]) => void; options: [string, string][] }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <MultiSelect ariaLabel={label} allLabel={all} value={value} onChange={onChange} options={options.map(([v, text]) => ({ value: v, label: text }))} />
    </div>
  );
}

/** Exports of every stage: the records of a screening stage or the extraction table, filtered
 *  by decision, exclusion reason, PDF, imported file and label, several values at once in each,
 *  with the number of records the file will hold before it is downloaded (D-39, D-41). */
export default function ExportsPage() {
  const t = useTranslations("review.exports");
  const { review } = useReview();
  const rid = review.id;
  const [stage, setStage] = useState<Stage>("ta");
  const [status, setStatus] = useState<string[]>([]);
  const [reason, setReason] = useState<string[]>([]);
  const [pdf, setPdf] = useState<string[]>([]);
  const [extraction, setExtraction] = useState("verified");
  const [file, setFile] = useState<string[]>([]);
  const [label, setLabel] = useState<string[]>([]);
  const [otherFiles, setOtherFiles] = useState<string[]>([]);
  const imports = useQuery<ImportRow[]>({ queryKey: ["imports", rid], queryFn: () => api.get(`/reviews/${rid}/imports`) });
  const labels = useQuery<LabelCount[]>({ queryKey: ["labels", rid], queryFn: () => api.get(`/reviews/${rid}/labels`) });

  // Only the filters shown for the stage are sent, each value as a repeated parameter. The
  // reason filter shows when the exclusions are part of the export.
  const withReasons = stage !== "extract" && (!status.length || status.includes("exclude"));
  const params = new URLSearchParams({ stage });
  const add = (key: string, values: string[]) => values.forEach((v) => params.append(key, v));
  if (stage === "extract") params.set("status", extraction);
  else {
    add("status", status);
    if (withReasons) add("reason", reason);
    if (stage === "ft") add("pdf", pdf);
  }
  add("import_id", file);
  add("label", label);
  const qs = params.toString();
  const count = useQuery<{ n: number }>({ queryKey: ["export-count", rid, qs], queryFn: () => api.get(`/reviews/${rid}/export/count?${qs}`) });
  const n = count.data?.n;
  const href = (fmt: string) => api.url(`/reviews/${rid}/export/${stage === "extract" ? "extractions" : "screening"}.${fmt}?${qs}`);
  const reasons: [string, string][] = [...review.criteria.exclusion_reasons.map((r): [string, string] => [r, r]), [NO_REASON, t("noReason")]];
  const fileOptions = (imports.data ?? []).map((i): [string, string] => [i.id, i.filename]);
  // The other exports cover every stage: only the file filter applies to them, PRISMA then
  // counting the searches of the files chosen alone (D-57).
  const otherParams = new URLSearchParams();
  otherFiles.forEach((f) => otherParams.append("import_id", f));
  const otherQs = otherFiles.length ? `?${otherParams}` : "";
  const others: [string, string][] = [
    [t("decisions"), `/reviews/${rid}/export/decisions.csv${otherQs}`],
    [t("prismaCounts"), `/reviews/${rid}/export/prisma.csv${otherQs}`],
    [t("allRecords"), `/reviews/${rid}/export/records.csv${otherQs}`],
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("text")} />
      <Card>
        <CardHeader><CardTitle>{t("records")}</CardTitle><CardDescription>{t(`stageText.${stage}`)}</CardDescription></CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Choice label={t("stage")} value={stage} onChange={(v) => setStage(v as Stage)} options={STAGES.map((s): [string, string] => [s, t(`stages.${s}`)])} />
            {stage === "extract" ? (
              <Choice label={t("extraction")} value={extraction} onChange={setExtraction} options={[["verified", t("extractionVerified")], ["all", t("extractionAll")]]} />
            ) : (
              <Filter label={t("decision")} all={t("allDecisions")} value={status} onChange={setStatus} options={STATUSES.map((s): [string, string] => [s, t(`statuses.${s}`)])} />
            )}
            {withReasons && <Filter label={t("reason")} all={t("allReasons")} value={reason} onChange={setReason} options={reasons} />}
            {stage === "ft" && <Filter label={t("pdf")} all={t("allPdfs")} value={pdf} onChange={setPdf} options={PDFS.map((p): [string, string] => [p, t(`pdfs.${p}`)])} />}
            <Filter label={t("file")} all={t("allFiles")} value={file} onChange={setFile} options={fileOptions} />
            <Filter label={t("label")} all={t("allLabels")} value={label} onChange={setLabel} options={(labels.data ?? []).map((l): [string, string] => [l.label, `${l.label} (${l.n})`])} />
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <p className="mr-auto text-sm text-muted-foreground" aria-live="polite">{n === undefined ? "…" : t(stage === "extract" ? "countStudies" : "countRecords", { n })}</p>
            {FORMATS.map((fmt) => n ? (
              <Button key={fmt} variant="outline" asChild><a href={href(fmt)}><Download />{t(`formats.${fmt}`)}</a></Button>
            ) : (
              <Button key={fmt} variant="outline" disabled><Download />{t(`formats.${fmt}`)}</Button>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{t("other")}</CardTitle><CardDescription>{t("otherText")}</CardDescription></CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Filter label={t("file")} all={t("allFiles")} value={otherFiles} onChange={setOtherFiles} options={fileOptions} />
          </div>
          <div className="flex flex-wrap gap-2 border-t border-border pt-4">
            {others.map(([text, path]) => <Button key={path} variant="outline" asChild><a href={api.url(path)}><Download />{text}</a></Button>)}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
