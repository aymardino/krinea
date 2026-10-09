import type { Metadata } from "next";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { Providers } from "@/lib/providers";
import { SITE_URL, localePath } from "@/lib/site";
import "../globals.css";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "seo" });
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: t("title"), template: "%s · Krinea" },
    description: t("description"),
    applicationName: "Krinea",
    alternates: {
      canonical: localePath(locale, ""),
      languages: Object.fromEntries(routing.locales.map((l) => [l, localePath(l, "")])),
    },
    openGraph: {
      type: "website", siteName: "Krinea", locale: locale === "fr" ? "fr_FR" : "en_GB",
      title: t("title"), description: t("description"), url: localePath(locale, ""),
      images: [{ url: "/brand/og.png", width: 1200, height: 630, alt: "Krinea" }],
    },
    twitter: { card: "summary_large_image", title: t("title"), description: t("description"), images: ["/brand/og.png"] },
  };
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  return (
    <html lang={locale} className="h-full" suppressHydrationWarning>
      <body className="min-h-full flex flex-col">
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
