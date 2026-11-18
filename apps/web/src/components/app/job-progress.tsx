"use client";

import { useTranslations } from "next-intl";
import type { Job } from "@/lib/api";
import { Progress } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

/** Where a long operation stands: waiting for the worker, then a bar that fills as the job
 *  reports progress (a moving bar until it first does). */
export function JobProgress({ job, label, className }: { job?: Job; label: string; className?: string }) {
  const t = useTranslations("common.job");
  const queued = !job || job.status === "queued";
  const pct = Math.round((job?.progress ?? 0) * 100);
  const known = !queued && pct > 0;
  return (
    <div role="status" aria-live="polite" className={cn("space-y-1.5", className)}>
      <p className="flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
        <span className="min-w-0 truncate"><span className="font-medium text-foreground">{label}</span> · {t(queued ? "queued" : "running")}</span>
        {known && <span className="shrink-0 tabular-nums">{pct}%</span>}
      </p>
      {known ? <Progress value={pct} aria-label={label} /> : (
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
          <div className="job-indeterminate absolute inset-y-0 left-0 w-1/3 rounded-full bg-brand-500" />
        </div>
      )}
    </div>
  );
}
