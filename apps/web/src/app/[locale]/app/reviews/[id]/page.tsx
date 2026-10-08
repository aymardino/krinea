"use client";

import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Activity as ActivityIcon, Users, Clock } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { api, type Activity } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/utils";
import { useReview } from "@/components/app/review-context";
import { RowBars, StackedBar, TimeBars } from "@/components/app/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Stat, Avatar } from "@/components/ui/misc";
import { Badge } from "@/components/ui/badge";

export default function OverviewPage() {
  const t = useTranslations("review.overview");
  const c = useTranslations("common");
  const locale = useLocale();
  const { review } = useReview();
  const s = review.counts;
  const activity = useQuery<Activity>({ queryKey: ["activity", review.id], queryFn: () => api.get(`/reviews/${review.id}/activity`) });
  const base = `/app/reviews/${review.id}`;
  const stages = ["ta", "ft"] as const;

  const perDay = (activity.data?.throughput ?? []).map((d) => ({
    label: d.day.slice(5), value: Object.entries(d).filter(([k]) => k !== "day").reduce((a, [, v]) => a + Number(v), 0),
  }));

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label={t("identified")} value={s.records} hint={`${s.unique} unique`} />
        <Stat label={t("duplicates")} value={s.duplicates} />
        <Stat label={t("toScreen")} value={s.stages.ta.my_left} hint={t("left", { n: s.stages.ta.pending })} tone="brand" />
        <Stat label={t("fullTexts")} value={s.stages.ft.my_left} hint={`${s.pdfs.available} PDF`} />
        <Stat label={t("included")} value={s.stages.ft.include} tone="include" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {stages.map((stage) => {
          const st = s.stages[stage];
          return (
            <Card key={stage}>
              <CardHeader className="flex-row items-start justify-between">
                <div><CardTitle>{t(`stage.${stage}`)}</CardTitle><CardDescription>{st.pool} records · {t("left", { n: st.my_left })}{st.my_seconds ? ` · ${t("timeSpent", { t: formatDuration(st.my_seconds) })}` : ""}</CardDescription></div>
                <Link href={`${base}/${stage === "ta" ? "screening" : "full-text"}`} className="text-sm text-primary hover:underline">{c("next")} →</Link>
              </CardHeader>
              <CardContent className="space-y-5">
                <StackedBar total={st.pool} segments={[
                  { key: "include", label: c("decision.include"), value: st.include, color: "var(--include)" },
                  { key: "maybe", label: c("decision.maybe"), value: st.maybe, color: "var(--maybe)" },
                  { key: "exclude", label: c("decision.exclude"), value: st.exclude, color: "var(--exclude)" },
                  { key: "conflict", label: c("decision.conflict"), value: st.conflict, color: "var(--conflict)" },
                  { key: "pending", label: c("decision.pending"), value: st.pending, color: "var(--pending)" },
                ]} />
                {st.conflict > 0 && <Badge variant="conflict">{t("conflicts", { n: st.conflict })}</Badge>}
                <div>
                  <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Users className="size-3.5" />{t("teamProgress")}</p>
                  <RowBars max={st.pool} rows={st.reviewers.map((r) => ({ label: r.name || r.email, value: r.done, hint: `${r.done}/${st.pool}${r.seconds ? ` · ${formatDuration(r.seconds)}` : ""}` }))} />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Clock className="size-4 text-brand-600" />{t("throughput")}</CardTitle></CardHeader>
          <CardContent>{perDay.length ? <TimeBars points={perDay} /> : <p className="text-sm text-muted-foreground">{t("noActivity")}</p>}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><ActivityIcon className="size-4 text-brand-600" />{t("activity")}</CardTitle></CardHeader>
          <CardContent>
            {!activity.data?.items.length ? <p className="text-sm text-muted-foreground">{t("noActivity")}</p> : (
              <ul className="divide-y divide-border text-sm">
                {activity.data.items.slice(0, 12).map((a, i) => (
                  <li key={i} className="flex items-center gap-3 py-2">
                    <Avatar name={a.user || "?"} className="size-7" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate"><span className="font-medium">{a.user}</span> <span className="text-muted-foreground">{a.kind.replace(/_/g, " ")}</span>{"n" in a.detail && <span className="text-muted-foreground"> · {String(a.detail.n)}</span>}{"filename" in a.detail && <span className="text-muted-foreground"> · {String(a.detail.filename)}</span>}</p>
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">{formatDate(a.at, locale)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
