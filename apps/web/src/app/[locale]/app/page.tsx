"use client";

import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Plus, Users, FileText, ChevronRight } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { api, type ReviewSummary } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState, PageHeader, Progress, Skeleton } from "@/components/ui/misc";

export default function ReviewsPage() {
  const t = useTranslations("reviews");
  const c = useTranslations("common");
  const locale = useLocale();
  const { data, isLoading } = useQuery<ReviewSummary[]>({ queryKey: ["reviews"], queryFn: () => api.get("/reviews") });
  return (
    <div className="mx-auto max-w-7xl 2xl:max-w-[1600px] px-4 py-8 sm:px-6">
      <PageHeader title={t("title")} actions={<Button asChild><Link href="/app/reviews/new"><Plus />{t("new")}</Link></Button>} />
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : !data?.length ? (
        <EmptyState icon={<FileText />} title={t("empty")} action={<Button asChild><Link href="/app/reviews/new"><Plus />{t("new")}</Link></Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.map((r) => (
            <Link key={r.id} href={`/app/reviews/${r.id}`} className="group rounded-xl border border-border bg-card p-5 shadow-card transition-colors hover:border-brand-400">
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-display text-lg font-semibold leading-snug group-hover:text-brand-800 dark:group-hover:text-brand-200">{r.title}</h2>
                <ChevronRight className="mt-1 size-4 shrink-0 text-muted-foreground" />
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary">{c(`role.${r.my_role}` as "role.owner")}</Badge>
                <span className="inline-flex items-center gap-1"><FileText className="size-3.5" />{t("records", { n: r.n_records })}</span>
                <span className="inline-flex items-center gap-1"><Users className="size-3.5" />{t("members", { n: r.n_members })}</span>
              </div>
              <div className="mt-4">
                <Progress value={Math.round(r.progress * 100)} />
                <p className="mt-1.5 flex justify-between text-xs text-muted-foreground"><span>{t("progress", { p: Math.round(r.progress * 100) })}</span><span>{formatDate(r.updated_at, locale)}</span></p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
