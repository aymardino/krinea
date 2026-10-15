"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, Pause, Play } from "lucide-react";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Kbd, Progress } from "@/components/ui/misc";
import { Highlight } from "@/components/app/highlight";
import { BrowserFrame } from "@/components/marketing/browser-frame";
import { cn } from "@/lib/utils";

/* Three records of the seeded sample review ("Solar mini-grids in sub-Saharan Africa: costs and
   outcomes"). They are fictitious literature written for the demo and stay in English in both
   locales, like review data in the application. */
type Decision = "include" | "maybe" | "exclude";
const RECORDS: { title: string; authors: string; year: string; journal: string; source: string; abstract: string; decision: Decision; key: string; reason?: string; note?: string }[] = [
  {
    title: "Comparing grid extension and solar mini-grids for last-mile electrification in Ethiopia",
    authors: "Tesfaye, Hanna; Haile, Meron; Walsh, Declan",
    year: "2017", journal: "Energy Policy", source: "Web of Science",
    abstract: "Ethiopia plans to reach universal access by extending the national grid, yet many settlements lie far from existing lines. We compare the cost of grid extension and of solar mini-grids for 1,860 unelectrified settlements using a geospatial least-cost model with settlement-level demand estimates.",
    decision: "include", key: "I",
  },
  {
    title: "Cost-benefit analysis of rural grid extension in southern Europe",
    authors: "Villanueva, Marta; Pereira, Ines; Castellanos, Diego",
    year: "2016", journal: "Utilities Policy", source: "Web of Science",
    abstract: "Remaining unconnected dwellings in rural Spain, Portugal and Italy are few but costly to reach. We perform a cost-benefit analysis of grid extension for 1,240 dwellings using distribution company cost data and estimates of consumer surplus.",
    decision: "exclude", key: "E", reason: "Wrong population / setting",
  },
  {
    title: "Willingness to pay for mini-grid electricity in rural Rwanda: a contingent valuation study",
    authors: "Nkurunziza, Jean-Claude; Petrova, Irina; Mutiso, Faith",
    year: "2019", journal: "World Development", source: "Web of Science",
    abstract: "We elicit willingness to pay for connection and monthly service from 780 households in 19 Rwandan villages selected for solar mini-grid development. Median willingness to pay for a basic connection was 24 USD, below the typical connection charge of 35 to 50 USD, while willingness to pay per kWh was close to prevailing mini-grid tariffs.",
    decision: "maybe", key: "M", note: "Tariffs reported, no cost figure: check at full text",
  },
];
const INCLUDE_KW = ["mini-grid*", "solar", "LCOE", "rural electrification", "techno-economic", "off-grid"];
const EXCLUDE_KW = ["grid extension", "nuclear", "review protocol"];
const DONE_START = 21;
const TOTAL = 51;

/* One scripted loop of about 11 seconds. Each step sets what the card shows and how long it
   stays; the chain is a single timeout per step, so pausing simply stops scheduling the next one. */
type Phase = "reset" | "enterQuiet" | "enter" | "press" | "release" | "decide" | "count" | "leave" | "hold";
type Step = { r: number; phase: Phase; ms: number };
function buildSteps(): Step[] {
  const steps: Step[] = [{ r: 0, phase: "reset", ms: 300 }, { r: 0, phase: "enterQuiet", ms: 1500 }];
  RECORDS.forEach((_, r) => {
    if (r > 0) steps.push({ r, phase: "enter", ms: 1500 });
    steps.push({ r, phase: "press", ms: 160 }, { r, phase: "release", ms: 40 }, { r, phase: "decide", ms: 200 }, { r, phase: "count", ms: 900 });
    steps.push(r < RECORDS.length - 1 ? { r, phase: "leave", ms: 400 } : { r, phase: "hold", ms: 1500 });
  });
  return steps;
}
const STEPS = buildSteps();
const DECIDED: Phase[] = ["decide", "count", "leave", "hold"];
const COUNTED: Phase[] = ["count", "leave", "hold"];

const reducedMotionQuery = () => (typeof window === "undefined" ? null : window.matchMedia("(prefers-reduced-motion: reduce)"));
function subscribeReduced(cb: () => void) {
  const mq = reducedMotionQuery();
  mq?.addEventListener("change", cb);
  return () => mq?.removeEventListener("change", cb);
}
const getReduced = () => reducedMotionQuery()?.matches ?? false;
const getReducedServer = () => false;

export function ScreeningDemo({ url }: { url: string }) {
  const t = useTranslations("marketing.demo");
  const c = useTranslations("common.decision");
  const reduced = useSyncExternalStore(subscribeReduced, getReduced, getReducedServer);
  // -1 is the static frame rendered on the server: record 1 decided, 22 / 51.
  const [step, setStep] = useState(-1);
  const [userPlaying, setUserPlaying] = useState(true);
  const [pageVisible, setPageVisible] = useState(true);
  const [inView, setInView] = useState(true);
  const frameRef = useRef<HTMLDivElement>(null);

  // Start the loop after hydration with a crossfade from the static frame (never under reduced motion).
  useEffect(() => {
    if (reduced) return;
    const id = window.setTimeout(() => setStep((s) => (s < 0 ? 0 : s)), 60);
    return () => window.clearTimeout(id);
  }, [reduced]);

  // Pause in hidden tabs and when the frame leaves the viewport; resume at the same step.
  useEffect(() => {
    const onVisibility = () => setPageVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", onVisibility);
    const el = frameRef.current;
    let io: IntersectionObserver | undefined;
    if (el && typeof IntersectionObserver !== "undefined") {
      io = new IntersectionObserver(([entry]) => setInView(!!entry?.isIntersecting), { threshold: 0.3 });
      io.observe(el);
    }
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      io?.disconnect();
    };
  }, []);

  const playing = !reduced && userPlaying && pageVisible && inView && step >= 0;
  useEffect(() => {
    if (!playing) return;
    const id = window.setTimeout(() => setStep((s) => (s + 1) % STEPS.length), STEPS[step].ms);
    return () => window.clearTimeout(id);
  }, [playing, step]);

  const current: Step = step < 0 || reduced ? { r: 0, phase: "count", ms: 0 } : STEPS[step];
  const rec = RECORDS[current.r];
  const decided = DECIDED.includes(current.phase);
  const pressed = current.phase === "press";
  const done = DONE_START + current.r + (COUNTED.includes(current.phase) ? 1 : 0);
  const anim = current.phase === "reset" ? "fade" : current.phase === "enter" ? "in" : current.phase === "leave" ? "out" : undefined;
  const status = decided ? rec.decision : "pending";

  const decisionClass = (d: Decision) =>
    cn(
      buttonVariants({ variant: d }),
      "demo-decision pointer-events-none select-none",
      d === "maybe" && !(decided && rec.decision === d) && "text-amber-700",
      decided && rec.decision === d && d === "include" && "border-include bg-include text-white",
      decided && rec.decision === d && d === "exclude" && "border-exclude bg-exclude text-white",
      decided && rec.decision === d && d === "maybe" && "border-amber-700 bg-amber-700 text-white",
    );
  const kbdClass = (k: string) =>
    cn("demo-kbd", pressed && rec.key === k && "border-ink-950 bg-ink-950 text-white", decided && rec.key === k && "border-white/40 bg-white/20 text-white");

  return (
    <div ref={frameRef}>
      <BrowserFrame
        url={url}
        actions={
          reduced ? null : (
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-ink-500 hover:text-ink-950"
              aria-pressed={!userPlaying}
              aria-label={userPlaying ? t("pause") : t("play")}
              title={userPlaying ? t("pause") : t("play")}
              onClick={() => setUserPlaying((p) => !p)}
            >
              {userPlaying ? <Pause /> : <Play />}
            </Button>
          )
        }
      >
        <div className="p-3 sm:p-4 md:p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[13px] text-ink-500">
            <span className="font-medium text-ink-700">{t("stage")}</span>
            <span className="flex items-center gap-3">
              <span className="tabular-nums">{t("progress", { done, total: TOTAL })}</span>
              <Progress tone="include" value={Math.round((done / TOTAL) * 100)} className="h-1 w-24 sm:w-32" aria-hidden="true" />
            </span>
          </div>

          <article key={current.r} data-anim={anim} className="demo-card rounded-xl border border-border bg-card shadow-card" aria-live="off">
            <div className="min-h-[15.5rem] p-4 sm:p-5">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="brand">{rec.year}</Badge>
                <Badge variant="secondary">{rec.journal}</Badge>
                <Badge variant="secondary">{rec.source}</Badge>
                <StatusBadge status={status} label={c(status)} />
              </div>
              <h3 className="font-display mt-3 text-lg font-semibold leading-snug text-ink-950 sm:text-xl"><Highlight text={rec.title} include={INCLUDE_KW} exclude={EXCLUDE_KW} /></h3>
              <p className="mt-1 text-sm text-ink-500">{rec.authors}</p>
              <p className="mt-4 text-sm leading-relaxed text-ink-700 2xl:text-[15px]"><Highlight text={rec.abstract} include={INCLUDE_KW} exclude={EXCLUDE_KW} /></p>
            </div>
            <div className="space-y-3 border-t border-border p-3 sm:p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className={cn("flex h-9 items-center justify-between rounded-md border border-input bg-card px-3 text-sm shadow-sm", decided && rec.reason ? "text-ink-950" : "text-ink-500")} aria-label={t("reason")}>
                  <span className="truncate">{decided && rec.reason ? rec.reason : t("reason")}</span>
                  <ChevronDown className="size-4 shrink-0 opacity-50" aria-hidden="true" />
                </div>
                <div className={cn("flex h-9 items-center rounded-md border border-input bg-card px-3 text-sm shadow-sm", decided && rec.note ? "text-ink-950" : "text-ink-500")} aria-label={t("note")}>
                  <span className="truncate">{decided && rec.note ? rec.note : t("note")}</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={decisionClass("include")}>{c("include")}<Kbd className={kbdClass("I")}>I</Kbd></span>
                <span className={decisionClass("maybe")}>{c("maybe")}<Kbd className={kbdClass("M")}>M</Kbd></span>
                <span className={decisionClass("exclude")}>{c("exclude")}<Kbd className={kbdClass("E")}>E</Kbd></span>
              </div>
              <p className="text-xs text-ink-500">{t("hint")}</p>
            </div>
          </article>
        </div>
      </BrowserFrame>
    </div>
  );
}
