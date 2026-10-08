"use client";

import { useLocale, useTranslations } from "next-intl";
import { Code2 } from "lucide-react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { TamisWordmark } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { useMe } from "@/lib/auth";

export function LanguageSwitch({ className }: { className?: string }) {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("common");
  return (
    <label className={className}>
      <span className="sr-only">{t("language")}</span>
      <select
        aria-label={t("language")}
        value={locale}
        onChange={(e) => router.replace(pathname, { locale: e.target.value as "en" | "fr" })}
        className="h-8 rounded-md border border-border bg-card px-2 text-sm"
      >
        <option value="en">English</option>
        <option value="fr">Français</option>
      </select>
    </label>
  );
}

export function SiteHeader() {
  const t = useTranslations("nav");
  const c = useTranslations("common");
  const { data: me } = useMe();
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center"><TamisWordmark /></Link>
        <nav className="hidden items-center gap-6 text-sm font-medium text-muted-foreground md:flex">
          <Link href="/#features" className="hover:text-foreground">{t("features")}</Link>
          <Link href="/pricing" className="hover:text-foreground">{t("pricing")}</Link>
          <a href="https://github.com/aymardino/systematic_review" className="inline-flex items-center gap-1.5 hover:text-foreground" target="_blank" rel="noreferrer"><Code2 className="size-4" />{t("github")}</a>
        </nav>
        <div className="flex items-center gap-2">
          <LanguageSwitch className="hidden sm:block" />
          {me ? (
            <Button asChild><Link href="/app">{t("app")}</Link></Button>
          ) : (
            <>
              <Button variant="ghost" asChild><Link href="/sign-in">{c("signIn")}</Link></Button>
              <Button asChild><Link href="/sign-up">{c("signUp")}</Link></Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  const t = useTranslations("marketing");
  return (
    <footer className="border-t border-border bg-muted/40">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:px-6">
        <TamisWordmark size={22} className="text-brand-700" />
        <p>{t("footer", { year: new Date().getFullYear() })}</p>
        <LanguageSwitch />
      </div>
    </footer>
  );
}
