import { setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { Check, Coffee } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Faq } from "@/components/marketing/faq";
import { REPO_URL, SUPPORT_URL } from "@/lib/site";
import { cn } from "@/lib/utils";

export default async function PricingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Pricing />;
}

const PLANS = ["free", "pro", "institution"] as const;
const FAQ_KEYS = ["free", "data", "import", "conflict", "ai", "selfhost"] as const;

const h2 = "font-display max-w-[24ch] text-balance text-[28px] font-semibold leading-[1.12] tracking-[-0.02em] text-ink-950 md:text-[34px] lg:text-[40px]";
const textLink = "link-grow font-medium text-brand-700 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500";

/** Three plans in one bordered block. Only the Free plan exists today; the two others are
 *  labelled as planned, and nothing on this page invents a limit or a customer. */
function Pricing() {
  const t = useTranslations("pricing");
  const m = useTranslations("marketing");
  const faq = FAQ_KEYS.map((k) => ({ key: k, q: m(`faq.items.${k}.q`), a: m(`faq.items.${k}.a`) }));
  return (
    <>
      <section className="bg-white">
        <div className="container-site py-14 md:py-20 lg:py-24">
          <div className="max-w-[36rem]">
            <h1 className="hero-in font-display max-w-[20ch] text-balance text-[32px] font-semibold leading-[1.08] tracking-[-0.025em] text-ink-950 md:text-[40px] lg:text-[44px]">{t("title")}</h1>
            <p className="hero-in mt-5 text-[17px] leading-[1.5] text-ink-700 md:text-[19px] lg:text-xl [animation-delay:70ms]">{t("subtitle")}</p>
          </div>

          <div className="mt-12 grid divide-y divide-border rounded-2xl border border-border bg-white md:grid-cols-3 md:divide-x md:divide-y-0">
            {PLANS.map((p) => {
              const available = p === "free";
              return (
                <div key={p} className="flex flex-col p-6 sm:p-8">
                  <div className="flex items-start justify-between gap-4">
                    <h2 className="text-lg font-semibold leading-[1.3] text-ink-950">{t(`plans.${p}.name`)}</h2>
                    <span className={cn("shrink-0 rounded-md px-2 py-0.5 text-[13px] font-medium leading-5", available ? "bg-brand-100 text-brand-800" : "bg-ink-100 text-ink-500")}>
                      {available ? t("available") : t("planned")}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-ink-500">{t(`plans.${p}.tagline`)}</p>
                  <p className="font-display mt-6 text-[40px] font-semibold leading-none tracking-[-0.02em] text-ink-950 tabular-nums">{t(`plans.${p}.price`)}</p>
                  <p className="mt-2 min-h-5 text-[13px] text-ink-500">{p === "pro" ? t("monthly") : ""}</p>
                  <ul className="mt-6 space-y-2.5 text-[15px] leading-relaxed text-ink-700">
                    {t.raw(`plans.${p}.features`).map((f: string) => (
                      <li key={f} className="flex items-start gap-2.5">
                        <Check className="mt-[5px] size-3.5 shrink-0 text-brand-600" aria-hidden="true" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-8 pt-2 md:mt-auto">
                    <Button className="w-full" variant={available ? "default" : "outline"} asChild>
                      <Link href={available ? "/sign-up" : "/contact"}>{t(`plans.${p}.cta`)}</Link>
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-10 grid lg:grid-cols-12">
            <ul className="divide-y divide-border border-y border-border text-[15px] leading-relaxed text-ink-700 lg:col-span-7">
              <li className="py-4">{t("paidSoon")}</li>
              <li className="py-4">
                {t("selfhost")}{" "}
                <a href={`${REPO_URL}#readme`} target="_blank" rel="noreferrer" className={textLink}>{m("closing.secondary")}</a>
              </li>
              <li className="py-4">
                {t("lowIncome")} <Link href="/contact" className={textLink}>{t("lowIncomeCta")}</Link>
              </li>
            </ul>
            {/* Voluntary support of the hosted edition: a donation buys nothing and unlocks nothing. */}
            <aside id="support" className="mt-8 scroll-mt-16 rounded-2xl border border-ink-200 bg-brand-50 p-6 lg:col-span-4 lg:col-start-9 lg:mt-0">
              <h2 className="text-lg font-semibold text-ink-950">{t("support.title")}</h2>
              <p className="mt-2 text-[15px] leading-relaxed text-ink-700">{t("support.text")}</p>
              <Button variant="outline" className="mt-5 bg-white" asChild>
                <a href={SUPPORT_URL} target="_blank" rel="noreferrer noopener"><Coffee />{t("support.cta")}</a>
              </Button>
              <p className="mt-3 text-[13px] leading-5 text-ink-500">{t("support.note")}</p>
            </aside>
          </div>
        </div>
      </section>

      <section id="faq" className="bg-white">
        <div className="container-site grid gap-10 border-t border-ink-200 py-14 md:py-20 lg:grid-cols-12 lg:py-24">
          <div className="lg:col-span-4">
            <h2 className={h2}>{t("faqTitle")}</h2>
          </div>
          <div className="lg:col-span-7 lg:col-start-6">
            <Faq items={faq} />
          </div>
        </div>
      </section>
    </>
  );
}
