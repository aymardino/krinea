import { cn } from "@/lib/utils";

/** The Krinea mark: a circle divided by a diagonal line; two filled dots on the side that is
 *  kept, one hollow dot on the side that is set aside. From Greek krinō: to separate, to judge. */
export function KrineaMark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={cn("shrink-0", className)} aria-hidden="true">
      <circle cx="16" cy="16" r="14" fill="currentColor" opacity="0.12" />
      <circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor" strokeWidth="2.2" />
      <path d="M24.5 7.5 L7.5 24.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="11" cy="11" r="2.4" fill="currentColor" />
      <circle cx="16.5" cy="7.5" r="1.7" fill="currentColor" />
      <circle cx="21" cy="21" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

export function KrineaWordmark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-brand-700 dark:text-brand-300", className)}>
      <KrineaMark size={size} />
      <span className="font-display text-[1.3em] font-bold tracking-tight text-foreground">Krinea</span>
    </span>
  );
}
