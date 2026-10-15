"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

type Tag = "div" | "section" | "ul" | "dl" | "li" | "p" | "figure";

/** Fades and lifts its children once, when they enter the viewport. CSS does the motion
 *  (see the .reveal rules in globals.css); this only flips a data attribute, and disconnects
 *  after the first intersection so nothing replays. Children with the class "reveal-item"
 *  stagger by 60ms. Without JavaScript the layout's noscript style shows everything. */
export function Reveal({ as = "div", delay = 0, className, children }: { as?: Tag; delay?: number; className?: string; children: React.ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      el.dataset.shown = "";
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          el.dataset.shown = "";
          io.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -10% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const Tag = as;
  return (
    <Tag ref={ref as never} className={cn("reveal", className)} style={delay ? { transitionDelay: `${delay}ms` } : undefined}>
      {children}
    </Tag>
  );
}
