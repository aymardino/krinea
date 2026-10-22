"use client";

import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api, type AdminOverview } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, PageHeader, Skeleton, Stat } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

/** One series, one hue, thin bars with a 2px gap; the hover title names the day and the value.
 *  Thirty days fit without labels on every bar: the first and last day are enough. */
function Bars({ days, values, label, format }: { days: string[]; values: number[]; label: string; format: (iso: string) => string }) {
  const max = Math.max(1, ...values);
  const w = 600;
  const h = 110;
  const gap = 2;
  const bw = (w - gap * (values.length - 1)) / values.length;
  return (
    <svg viewBox={`0 0 ${w} ${h + 20}`} className="h-auto w-full" role="img" aria-label={label}>
      {values.map((v, i) => {
        const bh = v === 0 ? 0 : Math.max(2, Math.round((v / max) * h));
        const x = i * (bw + gap);
        return (
          <g key={days[i]}>
            <title>{`${format(days[i])}: ${v}`}</title>
            <rect x={x} y={h - bh} width={bw} height={bh} rx={2} className="fill-brand-600 transition-colors hover:fill-brand-800" />
            <rect x={x} y={0} width={bw} height={h} className="fill-transparent" />
          </g>
        );
      })}
      <line x1={0} x2={w} y1={h + 0.5} y2={h + 0.5} className="stroke-ink-200" />
      <text x={0} y={h + 15} className="fill-ink-500 text-[11px]">{format(days[0])}</text>
      <text x={w} y={h + 15} textAnchor="end" className="fill-ink-500 text-[11px]">{format(days[days.length - 1])}</text>
    </svg>
  );
}

export default function AdminPage() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const { data: me } = useMe();
  const overview = useQuery<AdminOverview>({
    queryKey: ["admin-overview"],
    queryFn: () => api.get("/admin/overview"),
    enabled: !!me?.is_admin,
    refetchInterval: 60_000,
  });
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
  const dateTime = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const fmtDay = (iso: string) => day.format(new Date(`${iso}T12:00:00`));
  const fmtDateTime = (iso: string | null) => (iso ? dateTime.format(new Date(iso.endsWith("Z") ? iso : `${iso}Z`)) : t("users.never"));
  const n = (v: number) => new Intl.NumberFormat(locale).format(v);

  if (me && !me.is_admin) {
    return <div className="mx-auto max-w-7xl p-6 2xl:max-w-[1600px]"><EmptyState title={t("adminsOnly")} /></div>;
  }
  const d = overview.data;
  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 2xl:max-w-[1600px]">
      <PageHeader title={t("title")} description={t("description")} />
      {!d ? (
        <div className="space-y-4"><Skeleton className="h-24 w-full" /><Skeleton className="h-40 w-full" /></div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{t("generated", { time: fmtDateTime(d.generated_at) })}</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label={t("totals.users")} value={n(d.totals.users)} hint={`${t("totals.verified")}: ${n(d.totals.verified)} · ${t("totals.google")}: ${n(d.totals.google)}`} />
            <Stat label={t("totals.signups7")} value={n(d.totals.signups_7d)} hint={`${t("totals.signups30")}: ${n(d.totals.signups_30d)}`} tone="brand" />
            <Stat label={t("totals.active7")} value={n(d.totals.active_7d)} hint={`${t("totals.active30")}: ${n(d.totals.active_30d)}`} tone="brand" />
            <Stat label={t("totals.reviews")} value={n(d.totals.reviews)} hint={`${t("totals.imports")}: ${n(d.totals.imports)}`} />
            <Stat label={t("totals.records")} value={n(d.totals.records)} />
            <Stat label={t("totals.decisions")} value={n(d.totals.decisions)} />
            <Stat label={t("totals.extractions")} value={n(d.totals.extractions)} hint={t("totals.extractionsVerified", { n: n(d.totals.extractions_verified) })} />
            <Stat label={t("totals.aiCalls")} value={n(d.totals.ai_calls)} hint={`${t("totals.aiTokens")}: ${n(d.totals.ai_tokens)}`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            {([["signups", d.series.signups], ["active", d.series.active], ["decisions", d.series.decisions]] as const).map(([key, values]) => (
              <Card key={key}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{t(`charts.${key}`)}</CardTitle>
                  <CardDescription>{t("charts.days")}{key === "active" ? ` · ${t("activeHint")}` : ""}</CardDescription>
                </CardHeader>
                <CardContent><Bars days={d.series.days} values={values} label={t(`charts.${key}`)} format={fmtDay} /></CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t("audience.title")}</CardTitle>
              <CardDescription>{t("audience.description")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label={t("audience.views7")} value={n(d.audience.views_7d)} />
                <Stat label={t("audience.views30")} value={n(d.audience.views_30d)} />
                <Stat label={t("audience.visitors7")} value={n(d.audience.visitors_7d)} hint={t("audience.visitorsHint")} tone="brand" />
                <Stat label={t("audience.visitors30")} value={n(d.audience.visitors_30d)} hint={t("audience.visitorsHint")} tone="brand" />
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <p className="mb-2 text-sm font-medium">{t("audience.viewsChart")} <span className="font-normal text-muted-foreground">({t("charts.days")})</span></p>
                  <Bars days={d.series.days} values={d.audience.series.views} label={t("audience.viewsChart")} format={fmtDay} />
                </div>
                <div>
                  <p className="mb-2 text-sm font-medium">{t("audience.visitorsChart")} <span className="font-normal text-muted-foreground">({t("charts.days")})</span></p>
                  <Bars days={d.series.days} values={d.audience.series.visitors} label={t("audience.visitorsChart")} format={fmtDay} />
                </div>
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <Table>
                  <THead><TR><TH>{t("audience.page")}</TH><TH className="text-right">{t("audience.views")}</TH></TR></THead>
                  <TBody>
                    {d.audience.pages.map((p) => <TR key={p.path}><TD className="font-medium">{p.path}</TD><TD className="text-right tabular-nums">{n(p.views)}</TD></TR>)}
                    {d.audience.pages.length === 0 ? <TR><TD colSpan={2} className="text-muted-foreground">{t("audience.empty")}</TD></TR> : null}
                  </TBody>
                </Table>
                <Table>
                  <THead><TR><TH>{t("audience.source")}</TH><TH className="text-right">{t("audience.views")}</TH></TR></THead>
                  <TBody>
                    {d.audience.referrers.map((r) => <TR key={r.host || "direct"}><TD className="font-medium">{r.host || t("audience.direct")}</TD><TD className="text-right tabular-nums">{n(r.views)}</TD></TR>)}
                    {d.audience.referrers.length === 0 ? <TR><TD colSpan={2} className="text-muted-foreground">{t("audience.empty")}</TD></TR> : null}
                  </TBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>{t("users.title")}</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <THead><TR><TH>{t("users.email")}</TH><TH>{t("users.name")}</TH><TH>{t("users.method")}</TH><TH>{t("users.verified")}</TH><TH className="text-right">{t("users.reviews")}</TH><TH>{t("users.created")}</TH><TH>{t("users.lastLogin")}</TH></TR></THead>
                <TBody>
                  {d.recent_users.map((u) => (
                    <TR key={u.id}>
                      <TD className="font-medium">{u.email}</TD>
                      <TD>{u.name}</TD>
                      <TD>{t(`users.methods.${u.method}`)}</TD>
                      <TD>{u.email_verified ? <Badge variant="brand">{t("users.yes")}</Badge> : <Badge variant="secondary">{t("users.no")}</Badge>}</TD>
                      <TD className="text-right tabular-nums">{n(u.reviews)}</TD>
                      <TD className="whitespace-nowrap">{fmtDateTime(u.created_at)}</TD>
                      <TD className="whitespace-nowrap">{fmtDateTime(u.last_login_at)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>{t("reviews.title")}</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <THead><TR><TH>{t("reviews.review")}</TH><TH>{t("reviews.owner")}</TH><TH className="text-right">{t("reviews.records")}</TH><TH className="text-right">{t("reviews.decisions")}</TH><TH className="text-right">{t("reviews.members")}</TH><TH>{t("reviews.updated")}</TH></TR></THead>
                <TBody>
                  {d.recent_reviews.map((r) => (
                    <TR key={r.id}>
                      <TD className="font-medium">{r.title}{r.is_archived ? <Badge variant="secondary" className="ml-2">{t("reviews.archived")}</Badge> : null}</TD>
                      <TD>{r.owner_email}</TD>
                      <TD className="text-right tabular-nums">{n(r.records)}</TD>
                      <TD className="text-right tabular-nums">{n(r.decisions)}</TD>
                      <TD className="text-right tabular-nums">{n(r.members)}</TD>
                      <TD className="whitespace-nowrap">{fmtDateTime(r.updated_at)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
