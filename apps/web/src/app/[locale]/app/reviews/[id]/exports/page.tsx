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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/ui/misc";

const STAGES = ["ta", "ft", "extract"] as const;
type Stage = (typeof STAGES)[number];
const STATUSES = ["include", "maybe", "exclude", "conflict", "pending"] as const;
const PDFS = ["available", "missing", "not_retrieved"] as const;
const FORMATS = ["ris", "csv", "xlsx"] as const;
const ALL = "__all__";      // no filter (a select item cannot have an empty value)
const NO_REASON = "-";      // exclusions given without a reason (NO_REASON in the API's exports.py)

/** One labelled select of the export form; `all`, when given, is the "no filter" choice. */
function Filter({ label, value, onChange, all, options }: { label: string; value: string; onChange: (v: string) => void; all?: string; options: [string, string][] }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          {all && <SelectItem value={ALL}>{all}</SelectItem>}
          {options.map(([v, text]) => <SelectItem key={v} value={v}>{text}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

/** Exports of every stage: the records of a screening stage or the extraction table, filtered
 *  by decision, exclusion reason, PDF, imported file and label, with the number of records the
 *  file will hold before it is downloaded (decision D-39). */
export default function ExportsPage() {
  const t = useTranslations("review.exports");
  const { review } = useReview();
  const rid = review.id;
  const [stage, setStage] = useState<Stage>("ta");
  const [status, setStatus] = useState(ALL);
  const [reason, setReason] = useState(ALL);
  const [pdf, setPdf] = useState(ALL);
  const [extraction, setExtraction] = useState("verified");
  const [file, setFile] = useState(ALL);
  const [label, setLabel] = useState(ALL);
  const imports = useQuery<ImportRow[]>({ queryKey: ["imports", rid], queryFn: () => api.get(`/reviews/${rid}/imports`) });
  const labels = useQuery<LabelCount[]>({ queryKey: ["labels", rid], queryFn: () => api.get(`/reviews/${rid}/labels`) });

  // Only the filters shown for the stage are sent.
  const params = new URLSearchParams({ stage });
  if (stage === "extract") params.set("status", extraction);
  else {
    if (status !== ALL) params.set("status", status);
    if (status === "exclude" && reason !== ALL) params.set("reason", reason);
    if (stage === "ft" && pdf !== ALL) params.set("pdf", pdf);
  }
  if (file !== ALL) params.set("import_id", file);
  if (label !== ALL) params.set("label", label);
  const qs = params.toString();
  const count = useQuery<{ n: number }>({ queryKey: ["export-count", rid, qs], queryFn: () => api.get(`/reviews/${rid}/export/count?${qs}`) });
  const n = count.data?.n;
  const href = (fmt: string) => api.url(`/reviews/${rid}/export/${stage === "extract" ? "extractions" : "screening"}.${fmt}?${qs}`);
  const reasons: [string, string][] = [...review.criteria.exclusion_reasons.map((r): [string, string] => [r, r]), [NO_REASON, t("noReason")]];
  const others: [string, string][] = [
    [t("decisions"), `/reviews/${rid}/export/decisions.csv`],
    [t("prismaCounts"), `/reviews/${rid}/export/prisma.csv`],
    [t("allRecords"), `/reviews/${rid}/export/records.csv`],
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("text")} />
      <Card>
        <CardHeader><CardTitle>{t("records")}</CardTitle><CardDescription>{t(`stageText.${stage}`)}</CardDescription></CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Filter label={t("stage")} value={stage} onChange={(v) => setStage(v as Stage)} options={STAGES.map((s): [string, string] => [s, t(`stages.${s}`)])} />
            {stage === "extract" ? (
              <Filter label={t("extraction")} value={extraction} onChange={setExtraction} options={[["verified", t("extractionVerified")], ["all", t("extractionAll")]]} />
            ) : (
              <Filter label={t("decision")} value={status} onChange={setStatus} all={t("allDecisions")} options={STATUSES.map((s): [string, string] => [s, t(`statuses.${s}`)])} />
            )}
            {stage !== "extract" && status === "exclude" && <Filter label={t("reason")} value={reason} onChange={setReason} all={t("allReasons")} options={reasons} />}
            {stage === "ft" && <Filter label={t("pdf")} value={pdf} onChange={setPdf} all={t("allPdfs")} options={PDFS.map((p): [string, string] => [p, t(`pdfs.${p}`)])} />}
            <Filter label={t("file")} value={file} onChange={setFile} all={t("allFiles")} options={(imports.data ?? []).map((i): [string, string] => [i.id, i.filename])} />
            <Filter label={t("label")} value={label} onChange={setLabel} all={t("allLabels")} options={(labels.data ?? []).map((l): [string, string] => [l.label, `${l.label} (${l.n})`])} />
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
        <CardHeader><CardTitle>{t("other")}</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {others.map(([text, path]) => <Button key={path} variant="outline" asChild><a href={api.url(path)}><Download />{text}</a></Button>)}
        </CardContent>
      </Card>
    </div>
  );
}
