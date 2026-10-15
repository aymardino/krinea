import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { CONTACT_EMAIL, REPO_URL } from "@/lib/site";

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

const TOPICS = ["institutions", "lowIncome", "support"] as const;
const textLink = "link-grow inline-block text-[15px] font-medium text-brand-700 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500";

/** Three topics as plain text blocks with a hairline above each, then the address.
 *  No icons, no tiles, no photograph: a stock face next to "a real person reads every
 *  message" would be the fake proof this site avoids. */
function Contact() {
  const t = useTranslations("contact");
  return (
    <section className="bg-white">
      <div className="container-site py-14 md:py-20 lg:py-24">
        <h1 className="hero-in font-display max-w-[20ch] text-balance text-[32px] font-semibold leading-[1.08] tracking-[-0.025em] text-ink-950 md:text-[40px] lg:text-[44px]">{t("title")}</h1>
        <p className="hero-in mt-5 max-w-[36rem] text-[17px] leading-[1.5] text-ink-700 md:text-[19px] lg:text-xl [animation-delay:70ms]">{t("lede")}</p>

        <div className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-3">
          {TOPICS.map((k) => (
            <div key={k} className="border-t border-ink-300 pt-5">
              <h2 className="text-lg font-semibold leading-[1.3] tracking-[-0.01em] text-ink-950">{t(`${k}.title`)}</h2>
              <p className="mt-3 max-w-[40ch] text-base leading-relaxed text-ink-700">{t(`${k}.text`)}</p>
              {k === "support" && (
                <p className="mt-5 flex flex-col items-start gap-2">
                  <a href={`${REPO_URL}/issues`} target="_blank" rel="noreferrer" className={textLink}>{t("support.issues")}</a>
                  <a href={`${REPO_URL}/discussions`} target="_blank" rel="noreferrer" className={textLink}>{t("support.discussions")}</a>
                </p>
              )}
            </div>
          ))}
        </div>

        <div className="mt-12 max-w-[40rem] border-t border-border pt-6">
          <p className="text-base leading-relaxed text-ink-700">
            {t("email")}{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="link-grow font-medium text-brand-700 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500">{CONTACT_EMAIL}</a>
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink-500">{t("response")}</p>
        </div>
      </div>
    </section>
  );
}
