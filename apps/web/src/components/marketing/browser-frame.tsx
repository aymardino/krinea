import { cn } from "@/lib/utils";

/** A plain browser window around a screenshot or a live demo: three dots, a URL pill, an
 *  optional actions slot at the right of the toolbar. Lifts 2px on hover (off under
 *  prefers-reduced-motion through the .frame-lift rule). */
export function BrowserFrame({ url, actions, className, children }: { url: string; actions?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("frame-lift overflow-hidden rounded-xl border border-brand-200 bg-white shadow-[0_24px_48px_-24px_rgb(15_31_58/0.25)]", className)}>
      <div className="flex h-8 items-center gap-3 border-b border-ink-200 bg-ink-50 px-3">
        <div className="flex shrink-0 gap-1.5" aria-hidden="true">
          <span className="size-2.5 rounded-full bg-ink-300" />
          <span className="size-2.5 rounded-full bg-ink-300" />
          <span className="size-2.5 rounded-full bg-ink-300" />
        </div>
        <div className="flex min-w-0 flex-1 justify-center">
          <span className="truncate rounded-md bg-ink-100 px-3 text-xs leading-6 text-ink-500">{url}</span>
        </div>
        <div className="flex w-[52px] shrink-0 justify-end">{actions}</div>
      </div>
      {children}
    </div>
  );
}
