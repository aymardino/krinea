import { setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { ArrowRight, Bot, FileSearch, GitMerge, ListChecks, Share2, Users, Lock } from "lucide-react";
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
  const steps = [
    { key: "import", icon: <FileSearch /> },
    { key: "dedup", icon: <GitMerge /> },
    { key: "screen", icon: <ListChecks /> },
    { key: "extract", icon: <Bot /> },
    { key: "report", icon: <Share2 /> },
  ] as const;
  return (
    <>
      <section className="mesh-bg relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-full bg-gradient-to-b from-transparent via-background/40 to-background" />
        <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-20 sm:px-6 md:pt-28">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-900 dark:border-brand-800 dark:bg-brand-950 dark:text-brand-100">{t("heroEyebrow")}</p>
          <h1 className="font-display max-w-3xl text-balance text-4xl font-semibold leading-[1.08] tracking-tight md:text-6xl">{t("heroTitle")}</h1>
          <p className="mt-6 max-w-2xl text-balance text-lg text-muted-foreground">{t("heroText")}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button size="lg" asChild><Link href="/sign-up">{t("ctaPrimary")}<ArrowRight /></Link></Button>
            <Button size="lg" variant="outline" asChild><a href="#features">{t("ctaSecondary")}</a></Button>
          </div>
          <p className="mt-6 text-sm text-muted-foreground">{t("trust")}</p>
        </div>
        <div className="relative mx-auto max-w-6xl px-4 pb-16 sm:px-6">
          <StagePreview />
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <h2 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{t("stepsTitle")}</h2>
        <ol className="mt-10 grid gap-5 md:grid-cols-5">
          {steps.map((s, i) => (
            <li key={s.key} className="rounded-xl border border-border bg-card p-5 shadow-card">
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg bg-brand-100 text-brand-800 dark:bg-brand-900 dark:text-brand-100 [&_svg]:size-5">{s.icon}</span>
                <span className="font-mono text-xs text-muted-foreground">0{i + 1}</span>
              </div>
              <h3 className="mt-4 text-lg font-semibold">{t(`steps.${s.key}.title`)}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t(`steps.${s.key}.text`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-border bg-muted/40">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-6 md:grid-cols-3">
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

      <section className="mx-auto max-w-6xl px-4 py-20 text-center sm:px-6">
        <h2 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{t("heroTitle")}</h2>
        <div className="mt-8 flex justify-center gap-3">
          <Button size="lg" asChild><Link href="/sign-up">{t("ctaPrimary")}<ArrowRight /></Link></Button>
          <Button size="lg" variant="outline" asChild><Link href="/pricing">Pricing</Link></Button>
        </div>
      </section>
    </>
  );
}
