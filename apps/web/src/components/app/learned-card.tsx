"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Lightbulb } from "lucide-react";
import { api, ApiError, type Job, type LearnedStatus } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { useJob } from "@/lib/use-job";
import { formatDate } from "@/lib/utils";
import { JobProgress } from "@/components/app/job-progress";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/misc";

/** How far the suggestions can be trusted, from their cross-validated AUC: the chance that a
 *  record you included scores above one you excluded. */
export function aucLevel(auc: number): "low" | "fair" | "good" | "high" {
  return auc < 0.75 ? "low" : auc < 0.85 ? "fair" : auc < 0.93 ? "good" : "high";
}

/** The rail panel of the suggestions learned from your own title/abstract decisions (D-54):
 *  how far you are from the decisions they need, the button that computes them (in the
 *  worker), and what the last run learned from, how reliable it is, and how many decisions
 *  you made since. `onReady` is called when a run ends well. */
export function LearnedCard({ reviewId, onReady }: { reviewId: string; onReady: () => void }) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const locale = useLocale();
  const qc = useQueryClient();
  const { data: me } = useMe();
  // Under the records key: each decision fetches it again, as it does the list.
  const status = useQuery<LearnedStatus>({ queryKey: ["records", reviewId, "learned"], queryFn: () => api.get(`/reviews/${reviewId}/learned`) });
  const job = useJob(reviewId, ["learn"], (j) => {
    if (j.status === "failed") toast.error(t("learnedFailed"), { description: j.error });
    else { toast.success(t("learnedDone")); onReady(); }
    qc.invalidateQueries({ queryKey: ["records", reviewId] });
  }, me?.id ?? "");
  const run = useMutation({
    mutationFn: () => api.post<Job>(`/reviews/${reviewId}/learned`),
    onSuccess: job.follow,
    onError: (e) => toast.error(e instanceof ApiError ? e.message : c("error")),
  });
  const running = run.isPending || job.running;
  const s = status.data;
  if (!s) return null;
  const n = s.n_include + s.n_exclude;
  const two = (x: number) => x.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Lightbulb className="size-3.5" />{t("learnedTitle")}</p>
      <p className="mt-2 text-[11px] leading-snug text-muted-foreground">{t("learnedIntro")}</p>
      {!s.ready && (
        <div className="mt-3 space-y-1.5">
          <Progress value={Math.min(100, Math.round((n / s.min_decisions) * 100))} aria-label={t("learnedTitle")} />
          <p className="text-[11px] text-muted-foreground">{t("learnedProgress", { n, min: s.min_decisions, inc: s.n_include, exc: s.n_exclude })}</p>
          <p className="text-[11px] text-muted-foreground">{t("learnedNeed", { min: s.min_decisions, each: s.min_each })}</p>
        </div>
      )}
      <Button className="mt-3 w-full" size="sm" variant={s.ready ? "default" : "outline"} disabled={!s.ready || running} onClick={() => run.mutate()}>
        {t(s.run ? "learnedRerun" : "learnedRun")}
      </Button>
      {running ? (
        <div className="mt-3 border-t border-border pt-3"><JobProgress job={job.job} label={t("learnedRunning")} /></div>
      ) : s.run && (
        <div className="mt-3 space-y-1.5 border-t border-border pt-3 text-[11px] leading-snug text-muted-foreground">
          <p>{t("learnedLast", { inc: s.run.n_include, exc: s.run.n_exclude, date: formatDate(s.run.created_at, locale) })}</p>
          {s.run.auc != null && <p>{t("learnedQuality", { level: t(`learnedLevel.${aucLevel(s.run.auc)}`), auc: two(s.run.auc) })}</p>}
          {s.new_since > 0 && <p className="text-foreground">{t("learnedNew", { n: s.new_since })}</p>}
          {(s.run.include_terms.length > 0 || s.run.exclude_terms.length > 0) && (
            <details>
              <summary className="cursor-pointer select-none hover:text-foreground">{t("learnedTerms")}</summary>
              {s.run.include_terms.length > 0 && <p className="mt-1"><span className="font-medium text-include">{t("learnedTermsInclude")}</span> {s.run.include_terms.join(", ")}</p>}
              {s.run.exclude_terms.length > 0 && <p className="mt-1"><span className="font-medium text-exclude">{t("learnedTermsExclude")}</span> {s.run.exclude_terms.join(", ")}</p>}
            </details>
          )}
          <p>{t("learnedHow")}</p>
        </div>
      )}
    </div>
  );
}
