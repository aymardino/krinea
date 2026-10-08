import { setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { ArrowRight, Bot, Download, FileCheck, FileSearch, GitMerge, ListChecks, Lock, Server, Share2, Unlock, Users } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { StagePreview } from "@/components/marketing/stage-preview";

export default async function LandingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Landing />;
}

function Landing() {
  const t = useTranslations("marketing");
  const nav = useTranslations("nav");
  const steps = [
    { key: "import", icon: <FileSearch /> },
    { key: "dedup", icon: <GitMerge /> },
    { key: "screen", icon: <ListChecks /> },
    { key: "extract", icon: <Bot /> },
    { key: "report", icon: <Share2 /> },
  ] as const;
  const facts = [
    { key: "eu", icon: <Server /> },
    { key: "oss", icon: <Unlock /> },
    { key: "prisma", icon: <FileCheck />, href: "https://www.prisma-statement.org/" },
    { key: "export", icon: <Download /> },
  ] as const;
  return (
    <>
      {/* Hero: text left, product right from lg up */}
      <section className="mesh-bg relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-background/40 to-background" />
        <div className="relative mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:py-16 lg:grid-cols-2 lg:items-center lg:gap-12 xl:gap-16">
          <div className="max-w-xl">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-900 dark:border-brand-800 dark:bg-brand-950 dark:text-brand-100">{t("heroEyebrow")}</p>
            <h1 className="font-display text-balance text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl xl:text-[3.5rem]">{t("heroTitle")}</h1>
            <p className="mt-5 max-w-lg text-balance text-base text-muted-foreground md:text-lg">{t("heroText")}</p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Button size="lg" className="w-full sm:w-auto" asChild><Link href="/sign-up">{t("ctaPrimary")}<ArrowRight /></Link></Button>
              <Button size="lg" variant="outline" className="w-full sm:w-auto" asChild><a href="#features">{t("ctaSecondary")}</a></Button>
            </div>
            <p className="mt-5 text-sm text-muted-foreground">{t("trust")}</p>
          </div>
          <div className="relative lg:-mr-6 xl:-mr-12">
            <StagePreview variant="hero" />
          </div>
        </div>
      </section>

      {/* Trust strip: four verifiable facts */}
      <section className="border-y border-border bg-muted/40">
        <ul className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-3 px-4 py-4 text-sm text-muted-foreground sm:px-6 md:flex md:items-center md:justify-between">
          {facts.map((f) => (
            <li key={f.key} className="flex items-center gap-2 [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-brand-700">
              {f.icon}
              {"href" in f ? <a href={f.href} target="_blank" rel="noreferrer" className="hover:text-foreground">{t(`trustStrip.${f.key}`)}</a> : <span>{t(`trustStrip.${f.key}`)}</span>}
            </li>
          ))}
        </ul>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-4 py-14 sm:px-6 md:py-20">
        <h2 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{t("stepsTitle")}</h2>
        <p className="mt-3 max-w-2xl text-lg text-muted-foreground">{t("stepsLede")}</p>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {steps.map((s, i) => (
            <li key={s.key} className={`rounded-xl border border-border bg-card p-5 shadow-card ${i === 4 ? "sm:col-span-2 lg:col-span-1" : ""}`}>
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg bg-brand-100 text-brand-800 dark:bg-brand-900 dark:text-brand-100 [&_svg]:size-5">{s.icon}</span>
                <span className="font-mono text-xs text-muted-foreground">0{i + 1}</span>
              </div>
              <h3 className="mt-4 text-base font-semibold">{t(`steps.${s.key}.title`)}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t(`steps.${s.key}.text`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-border bg-muted/40">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3 md:gap-10 md:py-20">
          {[
            { icon: <Bot />, title: t("aiTitle"), text: t("aiText") },
            { icon: <Users />, title: t("teamTitle"), text: t("teamText") },
            { icon: <Lock />, title: t("openTitle"), text: t("openText") },
          ].map((f) => (
            <div key={f.title}>
              <span className="inline-flex size-10 items-center justify-center rounded-lg bg-card text-brand-700 shadow-card [&_svg]:size-5">{f.icon}</span>
              <h3 className="mt-4 font-display text-2xl font-semibold">{f.title}</h3>
              <p className="mt-2 leading-relaxed text-muted-foreground">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing teaser */}
      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 md:py-20">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-card md:flex md:items-center md:justify-between md:gap-8 md:p-8">
          <div>
            <h2 className="font-display text-2xl font-semibold tracking-tight">{t("pricingTeaser.title")}</h2>
            <p className="mt-2 max-w-2xl text-muted-foreground">{t("pricingTeaser.text")}</p>
          </div>
          <Button variant="outline" size="lg" className="mt-5 shrink-0 md:mt-0" asChild><Link href="/pricing">{t("pricingTeaser.cta")}</Link></Button>
        </div>
      </section>

      {/* Closing */}
      <section className="mx-auto max-w-6xl px-4 pb-20 pt-4 text-center sm:px-6">
        <h2 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{t("closingTitle")}</h2>
        <p className="mx-auto mt-4 max-w-2xl text-balance text-muted-foreground">{t("closingText")}</p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Button size="lg" asChild><Link href="/sign-up">{t("ctaPrimary")}<ArrowRight /></Link></Button>
          <Button size="lg" variant="outline" asChild><Link href="/pricing">{nav("pricing")}</Link></Button>
        </div>
      </section>
    </>
  );
}
