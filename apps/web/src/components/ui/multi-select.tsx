"use client";

import { ChevronDown } from "lucide-react";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export type MultiOption = { value: string; label: string };

/** A filter whose options can be ticked several at once (D-41): a record shows when it matches
 *  any of them. Nothing ticked means no filter, the `allLabel` choice, which unticks the others.
 *  The menu stays open while options are ticked; the button lists what is ticked. */
export function MultiSelect({ options, value, onChange, allLabel, ariaLabel, className }: {
  options: MultiOption[]; value: string[]; onChange: (value: string[]) => void; allLabel: string; ariaLabel?: string; className?: string;
}) {
  // A value ticked before its option went away (a label no record has any more) still filters,
  // so it still shows.
  const names = new Map(options.map((o) => [o.value, o.label]));
  const text = value.length ? value.map((v) => names.get(v) ?? v).join(", ") : allLabel;
  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label={ariaLabel} title={text}
                           className={cn("flex h-9 w-full items-center justify-between gap-2 whitespace-nowrap rounded-md border border-input bg-card px-3 py-2 text-left text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring", className)}>
        <span className="min-w-0 truncate">{text}</span>
        {value.length > 1 && <span className="ml-auto shrink-0 rounded-full bg-brand-50 px-1.5 text-[11px] font-medium tabular-nums text-brand-800 dark:bg-brand-950 dark:text-brand-200">{value.length}</span>}
        <ChevronDown className="size-4 shrink-0 opacity-50" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-96 min-w-[var(--radix-dropdown-menu-trigger-width)] overflow-y-auto">
        <DropdownMenuCheckboxItem checked={!value.length} onCheckedChange={() => onChange([])} onSelect={(e) => e.preventDefault()}>{allLabel}</DropdownMenuCheckboxItem>
        <DropdownMenuSeparator />
        {options.map((o) => (
          <DropdownMenuCheckboxItem key={o.value} checked={value.includes(o.value)} onCheckedChange={() => toggle(o.value)} onSelect={(e) => e.preventDefault()}>
            {o.label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
