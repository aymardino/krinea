"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Code2, Menu } from "lucide-react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { KrineaWordmark } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useMe } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const REPO_URL = "https://github.com/aymardino/systematic_review";

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
        className={cn("h-8 rounded-md text-sm", bare ? "border-0 bg-transparent px-1 text-muted-foreground hover:text-foreground" : "border border-border bg-card px-2")}
      >
        <option value="en">English</option>
        <option value="fr">Français</option>
      </select>
    </label>
  );
}

const NAV: { key: "features" | "pricing" | "about"; href: string }[] = [
  { key: "features", href: "/#features" },
  { key: "pricing", href: "/pricing" },
  { key: "about", href: "/about" },
];

export function SiteHeader() {
  const t = useTranslations("nav");
  const c = useTranslations("common");
  const { data: me } = useMe();
  const [open, setOpen] = useState(false);
  const auth = me ? (
    <Button asChild><Link href="/app">{t("app")}</Link></Button>
  ) : (
    <>
      <Button variant="ghost" className="hidden sm:inline-flex" asChild><Link href="/sign-in">{c("signIn")}</Link></Button>
      <Button asChild><Link href="/sign-up">{c("signUp")}</Link></Button>
    </>
  );
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center"><KrineaWordmark /></Link>
        <nav className="hidden items-center gap-7 text-sm font-medium text-muted-foreground md:flex" aria-label="Main">
          {NAV.map((n) => <Link key={n.key} href={n.href} className="hover:text-foreground">{t(n.key)}</Link>)}
        </nav>
        <div className="flex items-center gap-1.5 sm:gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="hidden md:inline-flex" asChild>
                <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label={t("github")}><Code2 className="size-4" /></a>
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t("github")}</TooltipContent>
          </Tooltip>
          <LanguageSwitch bare className="hidden sm:block" />
          {auth}
          <Button variant="ghost" size="icon" className="md:hidden" aria-label={t("menu")} onClick={() => setOpen(true)}><Menu className="size-5" /></Button>
        </div>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="top-4 max-w-sm translate-y-0 sm:top-[10%]">
          <DialogTitle className="font-display text-lg">{t("menu")}</DialogTitle>
          <nav className="mt-2 flex flex-col gap-1 text-base" aria-label="Mobile">
            {NAV.map((n) => <Link key={n.key} href={n.href} onClick={() => setOpen(false)} className="rounded-md px-2 py-2 hover:bg-muted">{t(n.key)}</Link>)}
            <a href={REPO_URL} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-md px-2 py-2 text-muted-foreground hover:bg-muted"><Code2 className="size-4" />{t("github")}</a>
          </nav>
          <div className="mt-3 flex flex-col gap-2 border-t border-border pt-4">
            <LanguageSwitch />
            {me ? (
              <Button asChild><Link href="/app" onClick={() => setOpen(false)}>{t("app")}</Link></Button>
            ) : (
              <>
                <Button variant="outline" asChild><Link href="/sign-in" onClick={() => setOpen(false)}>{c("signIn")}</Link></Button>
                <Button asChild><Link href="/sign-up" onClick={() => setOpen(false)}>{c("signUp")}</Link></Button>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </header>
  );
}
