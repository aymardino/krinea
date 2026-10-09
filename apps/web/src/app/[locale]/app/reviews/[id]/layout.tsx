"use client";

import { use } from "react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { ReviewProvider, useReviewQuery } from "@/components/app/review-context";
import { Skeleton } from "@/components/ui/misc";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export default function ReviewLayout({ children, params }: { children: React.ReactNode; params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("review.tabs");
  const pathname = usePathname();
  const { data: review, isLoading, error } = useReviewQuery(id);
  if (isLoading) return <div className="mx-auto max-w-7xl 2xl:max-w-[1600px] p-6"><Skeleton className="h-9 w-80" /><Skeleton className="mt-6 h-64" /></div>;
  if (error || !review) return <div className="p-10 text-center text-exclude">{String(error ?? "Not found")}</div>;
  const s = review.counts;
  const base = `/app/reviews/${id}`;
  const tabs = [
    { href: base, label: t("overview") },
    { href: `${base}/data`, label: t("data"), n: s.records },
    { href: `${base}/screening`, label: t("screening"), n: s.stages.ta.my_left },
    { href: `${base}/full-text`, label: t("fulltext"), n: s.stages.ft.my_left },
    { href: `${base}/extraction`, label: t("extraction"), n: s.extraction.pool },
    { href: `${base}/prisma`, label: t("prisma") },
    { href: `${base}/settings`, label: t("settings") },
  ];
  return (
    <ReviewProvider review={review}>
      <div className="border-b border-border bg-card">
        <div className="mx-auto max-w-7xl 2xl:max-w-[1600px] px-4 pt-5 sm:px-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h1 className="font-display text-2xl font-semibold tracking-tight">{review.title}</h1>
            <span className="text-xs text-muted-foreground">{review.review_type}</span>
          </div>
          <nav className="-mb-px mt-4 flex gap-1 overflow-x-auto text-sm">
            {tabs.map((tab) => {
              const active = tab.href === base ? pathname === base : pathname.startsWith(tab.href);
              return (
                <Link key={tab.href} href={tab.href} className={cn("inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 font-medium transition-colors", active ? "border-brand-600 text-brand-800 dark:text-brand-200" : "border-transparent text-muted-foreground hover:text-foreground")}>
                  {tab.label}
                  {typeof tab.n === "number" && tab.n > 0 && <Badge variant={active ? "brand" : "secondary"} className="px-1.5 py-0 text-[11px]">{tab.n}</Badge>}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
      <div className="mx-auto max-w-7xl 2xl:max-w-[1600px] px-4 py-6 sm:px-6">{children}</div>
    </ReviewProvider>
  );
}
