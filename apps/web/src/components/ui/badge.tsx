import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors", {
  variants: {
    variant: {
      default: "border-transparent bg-primary text-primary-foreground",
      secondary: "border-transparent bg-muted text-foreground",
      outline: "text-foreground",
      brand: "border-transparent bg-brand-100 text-brand-900 dark:bg-brand-900 dark:text-brand-100",
      include: "border-transparent bg-include-bg text-include",
      maybe: "border-transparent bg-maybe-bg text-maybe",
      exclude: "border-transparent bg-exclude-bg text-exclude",
      conflict: "border-transparent bg-conflict-bg text-conflict",
      pending: "border-transparent bg-pending-bg text-pending",
    },
  },
  defaultVariants: { variant: "default" },
});

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const v = (["include", "maybe", "exclude", "conflict", "pending"].includes(status) ? status : "pending") as BadgeProps["variant"];
  return <Badge variant={v}>{label ?? status}</Badge>;
}
