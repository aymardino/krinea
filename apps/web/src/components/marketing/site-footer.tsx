"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { KrineaWordmark } from "@/components/brand/logo";
import { LanguageSwitch } from "@/components/marketing/site-header";
import { APP_VERSION, REPO_URL } from "@/lib/site";

type FooterLink = { label: string; href: string; external?: boolean };

export function SiteFooter() {
  const t = useTranslations("nav");
  const m = useTranslations("marketing");
  const c = useTranslations("common");
  const year = new Date().getFullYear();
  const groups: { key: string; title: string; links: FooterLink[] }[] = [
    { key: "product", title: t("footer.product"), links: [
      { label: t("howItWorks"), href: "/#how-it-works" },
      { label: t("pricing"), href: "/pricing" },
      { label: t("footer.selfHost"), href: `${REPO_URL}#readme`, external: true },
      { label: t("footer.releases"), href: `${REPO_URL}/releases`, external: true },
    ] },
    { key: "resources", title: t("footer.resources"), links: [
      { label: t("docs"), href: `${REPO_URL}#readme`, external: true },
      { label: t("footer.prisma"), href: "https://www.prisma-statement.org/", external: true },
      { label: t("footer.security"), href: "/security" },
    ] },
    { key: "project", title: t("footer.project"), links: [
      { label: t("about"), href: "/about" },
      { label: t("footer.contact"), href: "/contact" },
      { label: t("github"), href: REPO_URL, external: true },
      { label: t("footer.cite"), href: "/about#how-to-cite" },
    ] },
    { key: "legal", title: t("footer.legal"), links: [
      { label: t("footer.privacy"), href: "/privacy" },
      { label: t("footer.terms"), href: "/terms" },
      { label: t("footer.legalNotice"), href: "/legal" },
    ] },
  ];
  return (
    <footer className="border-t border-border bg-ink-50">
      <div className="container-site pb-10 pt-14 lg:pt-16">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_1fr]">
          <div className="space-y-4 sm:col-span-2 lg:col-span-1">
            <KrineaWordmark size={24} />
            <p className="text-sm text-ink-700">{c("tagline")}</p>
            <p className="max-w-xs text-[13px] leading-5 text-ink-500">{t("footer.independence")}</p>
            <LanguageSwitch />
          </div>
          {groups.map((g) => (
            <div key={g.key}>
              <p className="text-[13px] font-medium text-ink-950">{g.title}</p>
              <ul className="mt-3 space-y-2 text-sm text-ink-500">
                {g.links.map((l) => (
                  <li key={l.label}>
                    {l.external ? (
                      <a href={l.href} target="_blank" rel="noreferrer" className="transition-colors duration-150 hover:text-ink-950">{l.label}</a>
                    ) : (
                      <Link href={l.href} className="transition-colors duration-150 hover:text-ink-950">{l.label}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-col gap-2 border-t border-border pt-6 text-[13px] text-ink-500 sm:flex-row sm:items-center sm:justify-between">
          <p>{m("footer", { year })}</p>
          <p>{t("footer.licences")} <span>· Krinea {APP_VERSION}</span></p>
        </div>
      </div>
    </footer>
  );
}
