import { setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { Check } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";

export default async function PricingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Pricing />;
}

function Pricing() {
  const t = useTranslations("pricing");
  const plans = ["free", "pro", "institution"] as const;
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
      <h1 className="font-display text-center text-4xl font-semibold tracking-tight md:text-5xl">{t("title")}</h1>
      <p className="mx-auto mt-4 max-w-2xl text-center text-lg text-muted-foreground">{t("subtitle")}</p>
      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {plans.map((p) => {
          const highlight = p === "pro";
          return (
            <div key={p} className={`relative flex flex-col rounded-2xl border p-7 shadow-card ${highlight ? "border-brand-500 bg-card ring-2 ring-brand-500/30" : "border-border bg-card"}`}>
              <h2 className="text-lg font-semibold">{t(`plans.${p}.name`)}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{t(`plans.${p}.tagline`)}</p>
              <p className="mt-6 font-display text-5xl font-semibold tracking-tight">{t(`plans.${p}.price`)}</p>
              {p !== "institution" && <p className="text-xs text-muted-foreground">{t("monthly")}</p>}
              <ul className="mt-6 space-y-2.5 text-sm">
                {t.raw(`plans.${p}.features`).map((f: string) => (
                  <li key={f} className="flex items-start gap-2"><Check className="mt-0.5 size-4 shrink-0 text-brand-600" />{f}</li>
                ))}
              </ul>
              <div className="mt-8">
                <Button className="w-full" variant={highlight ? "default" : "outline"} asChild>
                  <Link href={p === "institution" ? "mailto:hello@tamis.app" : "/sign-up"}>{t(`plans.${p}.cta`)}</Link>
                </Button>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-10 text-center text-sm text-muted-foreground">{t("selfhost")}</p>
      <p className="mt-2 text-center text-sm text-muted-foreground">{t("lowIncome")}</p>
    </section>
  );
}
