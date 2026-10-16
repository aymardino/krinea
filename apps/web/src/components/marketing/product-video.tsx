"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Pause, Play } from "lucide-react";
import { cn } from "@/lib/utils";

/** The 40-second product tour (apps/video), one MP4 and one WebM per language under public/video.
 *  Silent, so it may start on its own: it plays while at least half of it is on screen and
 *  pauses otherwise, never under prefers-reduced-motion (then the poster and the play button
 *  remain). The file is only fetched once the element is near the viewport. */
export function ProductVideo({ className }: { className?: string }) {
  const locale = useLocale();
  const t = useTranslations("marketing.video");
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const base = `/video/krinea-tour-${locale === "fr" ? "fr" : "en"}`;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    el.muted = true;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        if (entry.isIntersecting && !reduced.matches) el.play().catch(() => {});
        else el.pause();
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  function toggle() {
    const el = ref.current;
    if (!el) return;
    if (el.paused) el.play().catch(() => {});
    else el.pause();
  }

  return (
    <figure className={className}>
      <div className="relative overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-[0_24px_60px_-30px_rgba(23,23,22,0.28)]">
        <video
          ref={ref}
          className="block aspect-video w-full bg-white"
          poster={`${base}-poster.jpg`}
          muted
          loop
          playsInline
          preload="metadata"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          aria-label={t("aria")}
        >
          {/* H.264 first (every browser, hardware decoding); VP9 for builds without H.264. */}
          <source src={`${base}.mp4`} type="video/mp4" />
          <source src={`${base}.webm`} type="video/webm" />
        </video>
        <button
          type="button"
          onClick={toggle}
          aria-label={playing ? t("pause") : t("play")}
          className={cn(
            "absolute bottom-4 left-4 inline-flex h-10 items-center gap-2 rounded-full border border-ink-200 bg-white/95 pl-3 pr-4 text-sm font-medium text-ink-950 shadow-sm backdrop-blur transition-colors hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2",
          )}
        >
          {playing ? <Pause className="size-4" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
          <span>{playing ? t("pause") : t("play")}</span>
        </button>
      </div>
      <figcaption className="mt-3 text-[13px] leading-5 text-ink-500">{t("caption")}</figcaption>
    </figure>
  );
}
