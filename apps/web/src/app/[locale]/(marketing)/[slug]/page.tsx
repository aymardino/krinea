import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { Markdown, ProseLayout } from "@/components/marketing/prose";

/** Markdown pages, one file per language under apps/web/content/<locale>/<slug>.md,
 *  rendered at build time. Legal texts stay editable without touching the code. */
const SLUGS = ["about", "privacy", "terms", "legal", "security"] as const;
type Slug = (typeof SLUGS)[number];

/* Alt text of the About photograph, from public/photos/CREDITS.md. */
const ABOUT_ALT: Record<string, string> = {
  en: "The clock tower of the Balme Library at the University of Ghana in Accra, framed by palm trees",
  fr: "La tour de l'horloge de la bibliothèque Balme de l'Université du Ghana, à Accra, entourée de palmiers",
};

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return routing.locales.flatMap((locale) => SLUGS.map((slug) => ({ locale, slug })));
}

function read(locale: string, slug: Slug): string | null {
  const file = path.join(process.cwd(), "content", locale, `${slug}.md`);
  try {
    return fs.readFileSync(file, "utf8");
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string; slug: string }> }): Promise<Metadata> {
  const { locale, slug } = await params;
  if (!SLUGS.includes(slug as Slug)) return {};
  const t = await getTranslations({ locale, namespace: "pages" });
  return { title: t(`${slug}.title`), description: t(`${slug}.description`), alternates: { languages: { en: `/${slug}`, fr: `/fr/${slug}` } } };
}

export default async function ContentPage({ params }: { params: Promise<{ locale: string; slug: string }> }) {
  const { locale, slug } = await params;
  if (!SLUGS.includes(slug as Slug)) notFound();
  setRequestLocale(locale);
  const source = read(locale, slug as Slug) ?? read("en", slug as Slug);
  if (!source) notFound();
  const t = await getTranslations({ locale, namespace: "pages" });
  const m = await getTranslations({ locale, namespace: "marketing" });
  /* About is the one reading page with a photograph: a place photo (the Balme Library in
     Accra), credited, never presented as an affiliation. The legal pages stay text only. */
  const image = slug === "about" ? { slug: "accra-balme-library" as const, alt: ABOUT_ALT[locale] ?? ABOUT_ALT.en, credit: m("about.photoCredit"), position: "50% 60%" } : undefined;
  return (
    <ProseLayout title={t(`${slug}.title`)} description={t(`${slug}.description`)} image={image}>
      <Markdown source={source} />
    </ProseLayout>
  );
}
