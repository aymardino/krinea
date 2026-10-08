import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { Building2, HeartHandshake, LifeBuoy, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { REPO_URL } from "@/components/marketing/site-header";

const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "pages" });
  return { title: t("contact.title"), description: t("contact.description") };
}

export default async function ContactPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Contact />;
}

function Contact() {
  const t = useTranslations("contact");
  const cards = [
    { key: "institutions", icon: <Building2 /> },
    { key: "lowIncome", icon: <HeartHandshake /> },
    { key: "support", icon: <LifeBuoy /> },
  ] as const;
  return (
    <section className="mx-auto max-w-5xl px-4 py-14 sm:px-6 md:py-20">
      <h1 className="font-display text-4xl font-semibold tracking-tight md:text-5xl">{t("title")}</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted-foreground">{t("lede")}</p>
      <div className="mt-10 grid gap-6 sm:grid-cols-3">
        {cards.map((c) => (
          <div key={c.key} className="rounded-xl border border-border bg-card p-6 shadow-card">
            <span className="inline-flex size-10 items-center justify-center rounded-lg bg-brand-100 text-brand-800 dark:bg-brand-900 dark:text-brand-100 [&_svg]:size-5">{c.icon}</span>
            <h2 className="mt-4 text-lg font-semibold">{t(`${c.key}.title`)}</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t(`${c.key}.text`)}</p>
            {c.key === "support" && (
              <div className="mt-4 flex flex-col gap-2">
                <Button variant="outline" size="sm" asChild><a href={`${REPO_URL}/issues`} target="_blank" rel="noreferrer">{t("support.issues")}</a></Button>
                <Button variant="ghost" size="sm" asChild><a href={`${REPO_URL}/discussions`} target="_blank" rel="noreferrer">{t("support.discussions")}</a></Button>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-10 flex items-start gap-3 rounded-xl border border-border bg-muted/40 p-5 text-sm">
        <Mail className="mt-0.5 size-4 shrink-0 text-brand-700" />
        <div>
          {CONTACT_EMAIL ? (
            <p>{t("email")} <a className="font-medium text-primary underline-offset-4 hover:underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
          ) : (
            <p className="text-muted-foreground">{t("emailSoon")}</p>
          )}
          <p className="mt-1 text-muted-foreground">{t("response")}</p>
        </div>
      </div>
    </section>
  );
}
