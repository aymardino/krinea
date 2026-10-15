"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Menu } from "lucide-react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { KrineaWordmark } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useMe } from "@/lib/auth";
import { REPO_URL } from "@/lib/site";
import { cn } from "@/lib/utils";

export function LanguageSwitch({ className, bare = false }: { className?: string; bare?: boolean }) {
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
        className={cn("h-8 rounded-md text-sm", bare ? "border-0 bg-transparent px-1 text-ink-500 hover:text-ink-950" : "border border-border bg-card px-2")}
      >
        <option value="en">English</option>
        <option value="fr">Français</option>
      </select>
    </label>
  );
}

const NAV: { key: "howItWorks" | "pricing" | "about"; href: string; path: string }[] = [
  { key: "howItWorks", href: "/#how-it-works", path: "/#how-it-works" },
  { key: "pricing", href: "/pricing", path: "/pricing" },
  { key: "about", href: "/about", path: "/about" },
];

/** Full-width header: wordmark at the far left of the viewport, primary button at the far right. */
export function SiteHeader() {
  const t = useTranslations("nav");
  const c = useTranslations("common");
  const m = useTranslations("marketing.hero");
  const pathname = usePathname();
  const { data: me } = useMe();
  const [open, setOpen] = useState(false);
  const primary = me ? (
    <Button asChild><Link href="/app">{t("app")}</Link></Button>
  ) : (
    <Button asChild><Link href="/sign-up"><span className="sm:hidden">{c("signUp")}</span><span className="hidden sm:inline">{m("primary")}</span></Link></Button>
  );
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-white/90 backdrop-blur">
      <div className="flex h-16 items-center px-4 sm:px-6 lg:px-8 xl:h-[72px]">
        <Link href="/" className="flex shrink-0 items-center" aria-label="Krinea"><KrineaWordmark /></Link>
        <nav className="ml-10 hidden items-center gap-8 text-[15px] font-medium text-ink-700 md:flex" aria-label="Main">
          {NAV.map((n) => {
            const active = n.path !== "/#how-it-works" && pathname === n.path;
            return (
              <Link key={n.key} href={n.href} aria-current={active ? "page" : undefined} className={cn("link-grow py-1 hover:text-ink-950", active && "text-ink-950")}>
                {t(n.key)}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:gap-4">
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="link-grow hidden text-[13px] text-ink-500 hover:text-ink-950 xl:inline">{t("source")}</a>
          <LanguageSwitch bare className="hidden sm:block" />
          {!me && <Button variant="ghost" className="hidden md:inline-flex" asChild><Link href="/sign-in">{c("signIn")}</Link></Button>}
          {primary}
          <Button variant="ghost" size="icon" className="md:hidden" aria-label={t("menu")} onClick={() => setOpen(true)}><Menu className="size-5" /></Button>
        </div>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="top-4 max-w-sm translate-y-0 sm:top-[10%]">
          <DialogTitle className="font-display text-lg">{t("menu")}</DialogTitle>
          <nav className="mt-2 flex flex-col gap-1 text-base" aria-label="Mobile">
            {NAV.map((n) => <Link key={n.key} href={n.href} onClick={() => setOpen(false)} className="rounded-md px-2 py-2 hover:bg-muted">{t(n.key)}</Link>)}
            <a href={REPO_URL} target="_blank" rel="noreferrer" className="rounded-md px-2 py-2 text-ink-500 hover:bg-muted">{t("github")}</a>
          </nav>
          <div className="mt-3 flex flex-col gap-2 border-t border-border pt-4">
            <LanguageSwitch />
            {me ? (
              <Button asChild><Link href="/app" onClick={() => setOpen(false)}>{t("app")}</Link></Button>
            ) : (
              <>
                <Button variant="outline" asChild><Link href="/sign-in" onClick={() => setOpen(false)}>{c("signIn")}</Link></Button>
                <Button asChild><Link href="/sign-up" onClick={() => setOpen(false)}>{m("primary")}</Link></Button>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </header>
  );
}
