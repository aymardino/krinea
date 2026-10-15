import { useFormatter, useLocale } from "next-intl";
import { cn } from "@/lib/utils";

/* Entries are refreshed by hand at each release and must match `git log` (newest first).
   Both languages are written here so the list reads naturally in each locale. */
const ENTRIES: { date: string; en: string; fr: string }[] = [
  {
    date: "2026-10-15",
    en: "New public site: blue palette, real screenshots, photographs and a live screening demo.",
    fr: "Nouveau site public : palette bleue, vraies captures d'écran, photographies et démonstration de tri en direct.",
  },
  {
    date: "2026-10-12",
    en: "Stored PDFs are deleted together with their review, records or import.",
    fr: "Les PDF stockés sont supprimés avec leur revue, leurs notices ou leur import.",
  },
  {
    date: "2026-10-12",
    en: "The worker purges old sign-in tokens and expired sessions every hour.",
    fr: "Le worker purge chaque heure les anciens jetons de connexion et les sessions expirées.",
  },
];

/** The three most recent changes, as a dated list. */
export function Changelog({ limit = 3, className }: { limit?: number; className?: string }) {
  const format = useFormatter();
  const locale = useLocale();
  return (
    <ol className={cn("divide-y divide-brand-200 border-y border-brand-200", className)}>
      {ENTRIES.slice(0, limit).map((e, i) => {
        const d = new Date(`${e.date}T00:00:00Z`);
        return (
          <li key={`${e.date}-${i}`} className="grid grid-cols-[112px_1fr] gap-4 py-4 sm:grid-cols-[120px_1fr]">
            <time dateTime={e.date} className="text-[13px] font-medium leading-6 tabular-nums text-ink-500">
              {format.dateTime(d, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })}
            </time>
            <p className="text-base leading-6 text-ink-950">{locale === "fr" ? e.fr : e.en}</p>
          </li>
        );
      })}
    </ol>
  );
}
