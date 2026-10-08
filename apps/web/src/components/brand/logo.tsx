import { cn } from "@/lib/utils";

/** The Tamis mark: a round sieve with a diagonal mesh. */
export function TamisMark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={cn("shrink-0", className)} aria-hidden="true">
      <defs>
        <clipPath id="tamis-clip">
          <circle cx="16" cy="16" r="12" />
        </clipPath>
      </defs>
      <circle cx="16" cy="16" r="14" fill="currentColor" opacity="0.12" />
      <circle cx="16" cy="16" r="12" fill="none" stroke="currentColor" strokeWidth="2.4" />
      <g clipPath="url(#tamis-clip)" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M2 10 L22 30 M6 4 L28 26 M10 0 L32 22 M0 16 L16 32" />
        <path d="M30 10 L10 30 M26 4 L4 26 M22 0 L0 22 M32 16 L16 32" />
      </g>
    </svg>
  );
}

export function TamisWordmark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-brand-700 dark:text-brand-300", className)}>
      <TamisMark size={size} />
      <span className="font-display text-[1.35em] font-semibold tracking-tight text-foreground">Tamis</span>
    </span>
  );
}
