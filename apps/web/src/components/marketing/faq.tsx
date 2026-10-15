import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/** Native details/summary list: zero dependencies, correct keyboard behaviour, only the
 *  chevron animates (and not under prefers-reduced-motion). Shared by the home and pricing pages. */
export function Faq({ items, className }: { items: { key: string; q: string; a: string }[]; className?: string }) {
  return (
    <div className={cn("divide-y divide-ink-200 border-y border-ink-200", className)}>
      {items.map((it) => (
        <details key={it.key} className="group">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-4 text-left text-lg font-medium text-ink-950 hover:text-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 [&::-webkit-details-marker]:hidden">
            <span>{it.q}</span>
            <ChevronDown className="size-4 shrink-0 text-ink-500 transition-transform duration-200 group-open:rotate-180" aria-hidden="true" />
          </summary>
          <p className="max-w-[38rem] pb-5 text-base leading-relaxed text-ink-700">{it.a}</p>
        </details>
      ))}
    </div>
  );
}
