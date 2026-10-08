import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { Markdown, ProseLayout } from "@/components/marketing/prose";

/** Markdown pages, one file per language under apps/web/content/<locale>/<slug>.md,
 *  rendered at build time. Legal texts stay editable without touching the code. */
const SLUGS = ["about", "privacy", "terms", "legal"] as const;
type Slug = (typeof SLUGS)[number];

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
  return (
    <ProseLayout title={t(`${slug}.title`)} description={t(`${slug}.description`)}>
      <Markdown source={source} />
    </ProseLayout>
  );
}
