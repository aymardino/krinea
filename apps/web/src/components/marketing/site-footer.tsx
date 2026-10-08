"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { TamisWordmark } from "@/components/brand/logo";
import { LanguageSwitch, REPO_URL } from "@/components/marketing/site-header";

type FooterLink = { key: string; href: string; external?: boolean };
const GROUPS: { key: "product" | "project" | "legal"; links: FooterLink[] }[] = [
  { key: "product", links: [
    { key: "features", href: "/#features" }, { key: "pricing", href: "/pricing" },
    { key: "selfHost", href: `${REPO_URL}#readme`, external: true }, { key: "releases", href: `${REPO_URL}/releases`, external: true },
  ] },
  { key: "project", links: [
    { key: "about", href: "/about" }, { key: "contact", href: "/contact" }, { key: "github", href: REPO_URL, external: true },
  ] },
  { key: "legal", links: [
    { key: "privacy", href: "/privacy" }, { key: "terms", href: "/terms" }, { key: "legalNotice", href: "/legal" },
  ] },
];

export function SiteFooter() {
  const t = useTranslations("nav");
  const m = useTranslations("marketing");
  const c = useTranslations("common");
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-border bg-muted/40">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div className="space-y-4">
            <TamisWordmark size={24} className="text-brand-700" />
            <p className="text-sm text-muted-foreground">{c("tagline")}</p>
            <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">{t("footer.independence")}</p>
            <LanguageSwitch />
          </div>
          {GROUPS.map((g) => (
            <div key={g.key}>
              <p className="text-xs font-semibold uppercase tracking-wide text-foreground">{t(`footer.${g.key}`)}</p>
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {g.links.map((l) => (
                  <li key={l.key}>
                    {l.external ? (
                      <a href={l.href} target="_blank" rel="noreferrer" className="hover:text-foreground">{t(l.key === "github" ? "github" : `footer.${l.key}`)}</a>
                    ) : (
                      <Link href={l.href} className="hover:text-foreground">{t(["features", "pricing", "about"].includes(l.key) ? l.key : `footer.${l.key}`)}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col gap-2 border-t border-border pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>{m("footer", { year })}</p>
          <p>{t("footer.licences")}</p>
        </div>
      </div>
    </footer>
  );
}
