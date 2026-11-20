"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, type Prisma } from "@/lib/api";
import { useReview } from "@/components/app/review-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Stat } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

const VARIANTS = ["new_v1", "new_v2", "updated_v1", "updated_v2"] as const;

export default function PrismaPage() {
  const t = useTranslations("review.prisma");
  const locale = useLocale();
  const { review } = useReview();
  const rid = review.id;
  const [variant, setVariant] = useState<(typeof VARIANTS)[number]>("new_v1");
  const counts = useQuery<Prisma>({ queryKey: ["prisma", rid], queryFn: () => api.get(`/reviews/${rid}/prisma`) });
  const svgUrl = api.url(`/reviews/${rid}/prisma.svg?variant=${variant}&lang=${locale}`);
  const c = counts.data;
  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("text")} actions={<>
        <Select value={variant} onValueChange={(v) => setVariant(v as typeof variant)}>
          <SelectTrigger className="w-72"><SelectValue /></SelectTrigger>
          <SelectContent>{VARIANTS.map((v) => <SelectItem key={v} value={v}>{t(`variants.${v}`)}</SelectItem>)}</SelectContent>
        </Select>
        <Button asChild><a href={`${svgUrl}&download=1`}><Download />{t("downloadSvg")}</a></Button>
      </>} />
      {c && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          <Stat label="Identified" value={c.identified} />
          <Stat label="Duplicates" value={c.duplicates_removed} />
          <Stat label="Screened" value={c.screened} />
          <Stat label="Sought" value={c.sought} />
          <Stat label="Assessed" value={c.assessed} />
          <Stat label="Included" value={c.included} tone="include" />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card><CardContent className="overflow-auto p-4"><img src={svgUrl} alt="PRISMA 2020 flow diagram" className="mx-auto max-w-full" /></CardContent></Card>
        <div className="space-y-6">
          {c && (
            <Card>
              <CardHeader><CardTitle>{t("bySource")}</CardTitle></CardHeader>
              <CardContent>
                <Table><THead><TR><TH>Source</TH><TH className="text-right">n</TH></TR></THead><TBody>{Object.entries(c.by_source).map(([k, v]) => <TR key={k}><TD>{k}</TD><TD className="text-right tabular-nums">{v}</TD></TR>)}</TBody></Table>
                {Object.keys(c.ft_excluded_reasons).length > 0 && (
                  <><p className="mb-2 mt-4 text-sm font-semibold">{t("reasons")}</p>
                  <Table><TBody>{Object.entries(c.ft_excluded_reasons).map(([k, v]) => <TR key={k}><TD>{k}</TD><TD className="text-right tabular-nums">{v}</TD></TR>)}</TBody></Table></>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
