"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BrowserFrame } from "@/components/marketing/browser-frame";

export type Stage = {
  key: string;
  label: string;
  stageLabel: string;
  title: string;
  bullets: string[];
  alt: string;
  src: string;
  width: number;
  height: number;
  url: string;
};

/** The five stages as tabs over the existing Radix Tabs: a hairline list with a 2px blue
 *  underline on the active trigger, one real screenshot per stage. Tabs never auto-advance;
 *  the incoming panel fades in 200ms (off under prefers-reduced-motion). */
export function HowItWorksTabs({ stages }: { stages: Stage[] }) {
  return (
    <Tabs defaultValue={stages[0]?.key}>
      <TabsList className="flex h-auto w-full items-stretch justify-start gap-6 overflow-x-auto rounded-none border-b border-brand-200 bg-transparent p-0 text-ink-500 sm:gap-8">
        {stages.map((s) => (
          <TabsTrigger
            key={s.key}
            value={s.key}
            className="-mb-px shrink-0 rounded-none bg-transparent px-0 py-3 text-[15px] font-medium text-ink-500 hover:text-ink-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 focus-visible:ring-0 data-[state=active]:bg-transparent data-[state=active]:text-ink-950 data-[state=active]:shadow-[inset_0_-2px_0_0_var(--brand-600)]"
          >
            {s.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {stages.map((s, i) => (
        <TabsContent key={s.key} value={s.key} className="tab-in mt-0 grid grid-cols-1 gap-8 pt-8 lg:min-h-[600px] lg:grid-cols-12 lg:items-start lg:gap-10 lg:pt-10 xl:gap-16">
          <div className="min-w-0 lg:col-span-4">
            <p className="text-[13px] font-medium tracking-[0.01em] text-ink-500">{s.stageLabel}</p>
            <h3 className="mt-2 max-w-[40ch] text-lg font-semibold leading-[1.3] tracking-[-0.01em] text-ink-950 lg:text-xl">{s.title}</h3>
            <ul className="mt-4 max-w-[34rem] list-disc space-y-2 pl-5 text-base leading-[1.55] text-ink-700 marker:text-ink-300">
              {s.bullets.map((b) => <li key={b}>{b}</li>)}
            </ul>
          </div>
          <div className="min-w-0 lg:col-span-8">
            <BrowserFrame url={s.url}>
              {/* eslint-disable-next-line @next/next/no-img-element -- lossless 2x capture served as is */}
              <img src={s.src} alt={s.alt} width={s.width} height={s.height} loading={i === 0 ? "eager" : "lazy"} decoding="async" className="block h-auto w-full" />
            </BrowserFrame>
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
