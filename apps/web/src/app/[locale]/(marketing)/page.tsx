import { setRequestLocale } from "next-intl/server";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Changelog } from "@/components/marketing/changelog";
import { Faq } from "@/components/marketing/faq";
import { HowItWorksTabs, type Stage } from "@/components/marketing/how-it-works-tabs";
import { Photo, PhotoCredit } from "@/components/marketing/photo";
import { Reveal } from "@/components/marketing/reveal";
import { ScreeningDemo } from "@/components/marketing/screening-demo";
import { APP_VERSION, REPO_URL, SITE_URL } from "@/lib/site";

const JSON_LD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Krinea",
  applicationCategory: "Research software",
  operatingSystem: "Web",
  url: SITE_URL,
  description: "Open-source workbench for systematic reviews: import references, remove duplicates, screen with your team, extract data with AI you verify, report with the PRISMA 2020 diagram.",
  license: "https://www.gnu.org/licenses/agpl-3.0.html",
  isAccessibleForFree: true,
  offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
  sameAs: [REPO_URL],
};
const ORG_LD = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Krinea",
  url: SITE_URL,
  logo: `${SITE_URL}/brand/krinea-mark-512.png`,
  sameAs: [REPO_URL],
};

const DEMO_URL = "krinea.org/app/reviews/solar-mini-grids/screening";
/* Captures of the sample review in public/screens (2x, 3:2), made by scripts/capture-screens.py. */
const SCREENS: { key: "import" | "dedup" | "screen" | "extract" | "report"; path: string; width: number; height: number }[] = [
  { key: "import", path: "data", width: 1964, height: 1308 },
  { key: "dedup", path: "data#duplicates", width: 2070, height: 1380 },
  { key: "screen", path: "screening", width: 2008, height: 1338 },
  { key: "extract", path: "extraction", width: 1440, height: 960 },
  { key: "report", path: "prisma", width: 2080, height: 1386 },
];
const FAQ_KEYS = ["free", "data", "import", "conflict", "ai", "selfhost"] as const;
const PRINCIPLE_KEYS = ["ai", "reason", "blind", "yours", "open", "lang"] as const;
const FACT_KEYS = ["licence", "imports", "screening", "reporting", "hosting"] as const;

export default async function LandingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Landing />;
}

const h2 = "font-display max-w-[24ch] text-balance text-[28px] font-semibold leading-[1.12] tracking-[-0.02em] text-ink-950 md:text-[34px] lg:text-[40px]";
const lede = "mt-5 max-w-[36rem] text-[17px] leading-[1.5] text-ink-700 md:text-[19px] lg:text-xl";
const textLink = "link-grow inline-block text-[15px] font-medium text-brand-700 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500";

function Landing() {
  const t = useTranslations("marketing");
  const locale = useLocale();
  const stages: Stage[] = SCREENS.map((s, i) => ({
    key: s.key,
    label: t(`how.tabs.${s.key}`),
    stageLabel: t("how.stage", { n: i + 1 }),
    title: t(`how.${s.key}.title`),
    bullets: [t(`how.${s.key}.b1`), t(`how.${s.key}.b2`), t(`how.${s.key}.b3`)],
    alt: t(`how.${s.key}.alt`),
    src: `/screens/${s.key}-${locale}.webp`,
    width: s.width,
    height: s.height,
    url: `krinea.org/app/reviews/solar-mini-grids/${s.path}`,
  }));
  const faq = FAQ_KEYS.map((k) => ({ key: k, q: t(`faq.items.${k}.q`), a: t(`faq.items.${k}.a`) }));

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_LD) }} />

      {/* Hero: text left, the live screening demo right, bleeding to the viewport edge from lg. */}
      <section id="top" className="overflow-x-clip bg-white">
        <div className="container-site grid gap-10 pb-16 pt-12 lg:grid-cols-12 lg:items-start lg:gap-10 lg:pb-24 lg:pt-16 xl:gap-12">
          <div className="max-w-[640px] lg:col-span-5 lg:pt-6">
            <h1 className="hero-in font-display text-balance text-4xl font-semibold leading-[1.06] tracking-[-0.025em] text-ink-950 sm:text-[44px] xl:text-[48px] 2xl:text-[52px]">{t("hero.title")}</h1>
            <p className="hero-in mt-5 max-w-[36rem] text-[17px] leading-[1.5] text-ink-700 md:text-[19px] lg:text-xl [animation-delay:70ms]">{t("hero.lede")}</p>
            <div className="hero-in mt-8 flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:gap-6 [animation-delay:140ms]">
              <Button size="lg" asChild><Link href="/sign-up">{t("hero.primary")}</Link></Button>
              <a href="#how-it-works" className="link-grow text-base font-medium text-brand-700 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500">{t("hero.secondary")}</a>
            </div>
            <p className="hero-in mt-4 text-sm text-ink-500 [animation-delay:210ms]">{t("hero.note")}</p>
          </div>
          <div className="hero-in min-w-0 lg:col-span-7 [animation-delay:280ms]">
            <div className="hero-bleed-right rounded-3xl bg-brand-50 p-4 sm:p-6 lg:rounded-r-none lg:rounded-l-3xl lg:p-10 lg:pr-8 xl:pr-10">
              <div className="lg:-ml-8">
                <ScreeningDemo url={DEMO_URL} />
              </div>
            </div>
            <p className="mt-3 text-[13px] leading-5 text-ink-500">{t("hero.demoCaption")}</p>
          </div>
        </div>
      </section>

      {/* Facts strip: the rhythm of a logo row, filled with checkable facts. */}
      <section id="facts" className="bg-white">
        <div className="container-site border-b border-ink-200 border-t-ink-300 border-t py-6">
          <Reveal as="dl" className="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
            {FACT_KEYS.map((k) => (
              <div key={k} className="reveal-item">
                <dt className="text-[13px] font-medium tracking-[0.01em] text-ink-500">{t(`facts.${k}.label`)}</dt>
                <dd className="mt-1 text-[15px] font-medium leading-snug text-ink-950">
                  {k === "reporting" ? <a href="https://www.prisma-statement.org/" target="_blank" rel="noreferrer" className="link-grow hover:text-brand-700">{t(`facts.${k}.value`)}</a> : t(`facts.${k}.value`)}
                </dd>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* How it works: five tabs, one real screenshot each, on a full-bleed tinted band. */}
      <section id="how-it-works" className="scroll-mt-16 bg-brand-50 py-14 md:py-20 lg:py-24 2xl:py-28">
        <div className="container-site">
          <Reveal className="max-w-[640px]">
            <h2 className={h2}>{t("how.title")}</h2>
            <p className={lede}>{t("how.lede")}</p>
          </Reveal>
          <Reveal className="mt-12" delay={90}>
            <HowItWorksTabs stages={stages} />
          </Reveal>
        </div>
      </section>

      {/* Photograph band: breathing space between the product and the people. */}
      <section className="bg-white">
        <Photo slug="library-laptop" alt={t("photoBand.alt")} sizes="100vw" width={1280} height={853} position="50% 45%" className="h-60 w-full md:h-80 lg:h-[420px]" />
        <div className="container-site pt-3">
          <Reveal as="p" className="text-[13px] leading-5 text-ink-500">{t("photoBand.caption")}</Reveal>
        </div>
      </section>

      {/* Origin story, in the maintainer's own words. */}
      <section id="story" className="bg-white py-14 md:py-20 lg:py-24 2xl:py-28">
        <div className="container-site grid gap-10 lg:grid-cols-12">
          <Reveal className="lg:col-span-5">
            <h2 className={h2}>{t("story.title")}</h2>
          </Reveal>
          <Reveal className="max-w-[38rem] space-y-5 text-[17px] leading-[1.6] text-ink-700 lg:col-span-6 lg:col-start-7" delay={70}>
            <p>{t("story.p1")}</p>
            <p>{t("story.p2")}</p>
            <p><Link href="/about" className={textLink}>{t("story.link")}</Link></p>
          </Reveal>
        </div>
      </section>

      {/* Two reviewers: the one section that shows two people working together. */}
      <section id="two-reviewers" className="bg-white">
        <div className="container-site border-t border-ink-200 py-14 md:py-20 lg:py-24 2xl:py-28">
          <div className="grid gap-10 lg:grid-cols-12 lg:items-center xl:gap-16">
            <Reveal as="figure" className="lg:col-span-6">
              <Photo slug="team-papers" alt={t("two.alt")} sizes="(min-width: 1024px) 55vw, 100vw" width={1280} height={853} position="50% 40%" className="aspect-[4/3] overflow-hidden rounded-2xl" />
              <PhotoCredit className="mt-3">{t("two.credit")}</PhotoCredit>
            </Reveal>
            <Reveal className="lg:col-span-5 lg:col-start-8" delay={90}>
              <h2 className={h2}>{t("two.title")}</h2>
              <p className={lede}>{t("two.lede")}</p>
              <ul className="mt-8 divide-y divide-border border-y border-border text-base leading-relaxed text-ink-700">
                <li className="reveal-item py-4">{t("two.f1")}</li>
                <li className="reveal-item py-4">{t("two.f2")}</li>
                <li className="reveal-item py-4">{t("two.f3")}</li>
              </ul>
              <p className="mt-6"><Link href="/sign-up" className={textLink}>{t("two.link")}</Link></p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* Principles: plain text cells with hairlines, no icons, no cards. */}
      <section id="principles" className="bg-white">
        <div className="container-site border-t border-ink-200 py-14 md:py-20 lg:py-24 2xl:py-28">
          <Reveal>
            <h2 className={h2}>{t("principles.title")}</h2>
          </Reveal>
          <Reveal className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3" delay={70}>
            {PRINCIPLE_KEYS.map((k) => (
              <div key={k} className="reveal-item border-t border-ink-300 pr-6 pt-5">
                <h3 className="max-w-[40ch] text-lg font-semibold leading-[1.3] tracking-[-0.01em] text-ink-950 lg:text-xl">{t(`principles.${k}.title`)}</h3>
                <p className="mt-3 max-w-[40ch] text-base leading-relaxed text-ink-700">{t(`principles.${k}.text`)}</p>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* Built in the open: dated facts from the repository. */}
      <section id="open" className="bg-brand-50 py-14 md:py-20 lg:py-24 2xl:py-28">
        <div className="container-site grid gap-10 lg:grid-cols-12 lg:items-start">
          <Reveal as="figure" className="lg:col-span-5">
            <Photo slug="highlighter-textbook" alt={t("open.alt")} sizes="(min-width: 1024px) 45vw, 100vw" width={1280} height={853} className="aspect-[4/3] overflow-hidden rounded-2xl" />
            <PhotoCredit className="mt-3">{t("open.credit")}</PhotoCredit>
          </Reveal>
          <div className="lg:col-span-6 lg:col-start-7">
            <Reveal delay={70}>
              <h2 className={h2}>{t("open.title")}</h2>
              <p className={lede}>{t("open.lede", { version: APP_VERSION })}</p>
            </Reveal>
            <Changelog className="mt-8" />
            <p className="mt-6 flex flex-wrap gap-x-8 gap-y-2">
              <a href={`${REPO_URL}/releases`} target="_blank" rel="noreferrer" className={textLink}>{t("open.releases")}</a>
              <a href={`${REPO_URL}/issues`} target="_blank" rel="noreferrer" className={textLink}>{t("open.roadmap")}</a>
            </p>
          </div>
        </div>
      </section>

      {/* Questions people ask first. */}
      <section id="faq" className="bg-white py-14 md:py-20 lg:py-24 2xl:py-28">
        <div className="container-site grid gap-10 lg:grid-cols-12">
          <Reveal className="lg:col-span-4">
            <h2 className={h2}>{t("faq.title")}</h2>
            <p className="mt-5 max-w-[36rem] text-base leading-relaxed text-ink-700">
              {t.rich("faq.more", {
                contact: (chunks) => <Link href="/contact" className="font-medium text-brand-700 underline underline-offset-4 hover:text-brand-800">{chunks}</Link>,
                discussions: (chunks) => <a href={`${REPO_URL}/discussions`} target="_blank" rel="noreferrer" className="font-medium text-brand-700 underline underline-offset-4 hover:text-brand-800">{chunks}</a>,
              })}
            </p>
          </Reveal>
          <Reveal className="lg:col-span-7 lg:col-start-6" delay={70}>
            <Faq items={faq} />
          </Reveal>
        </div>
      </section>

      {/* Closing band: one last calm ask. */}
      <section id="start" className="bg-brand-50 py-20">
        <Reveal className="container-site">
          <div className="max-w-[640px]">
            <h2 className={h2}>{t("closing.title")}</h2>
            <p className={lede}>{t("closing.lede")}</p>
          </div>
          <div className="reveal-item mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button size="lg" asChild><Link href="/sign-up">{t("closing.primary")}</Link></Button>
            <Button size="lg" variant="outline" asChild><a href={`${REPO_URL}#readme`} target="_blank" rel="noreferrer">{t("closing.secondary")}</a></Button>
          </div>
        </Reveal>
      </section>
    </>
  );
}

