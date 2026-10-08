import { Badge } from "@/components/ui/badge";
import { Kbd } from "@/components/ui/misc";

/** A static, illustrative screening card for the landing page. */
export function StagePreview() {
  return (
    <div className="mx-auto max-w-4xl overflow-hidden rounded-2xl border border-border bg-card shadow-pop">
      <div className="flex items-center justify-between border-b border-border bg-muted/50 px-4 py-2 text-xs text-muted-foreground">
        <div className="flex gap-1.5"><span className="size-2.5 rounded-full bg-border" /><span className="size-2.5 rounded-full bg-border" /><span className="size-2.5 rounded-full bg-border" /></div>
        <span>Title & abstract · 1 318 / 7 759</span>
        <div className="flex gap-1"><Kbd>I</Kbd><Kbd>M</Kbd><Kbd>E</Kbd></div>
      </div>
      <div className="grid gap-0 md:grid-cols-[220px_1fr]">
        <aside className="hidden border-r border-border p-3 md:block">
          {["Techno-economic assessment of solar PV mini-grids in Kenya", "Optimal sizing of a hybrid PV-diesel mini-grid in Nigeria", "Grid extension policy in Europe: a historical review", "LCOE of solar mini-grids in Tanzania: 30 sites"].map((s, i) => (
            <div key={s} className={`mb-1 rounded-md px-2 py-1.5 text-xs ${i === 1 ? "bg-brand-50 text-brand-900 dark:bg-brand-900 dark:text-brand-100" : "text-muted-foreground"}`}>{s}</div>
          ))}
        </aside>
        <div className="p-5">
          <div className="flex flex-wrap gap-2"><Badge variant="brand">2020</Badge><Badge variant="secondary">Renewable Energy</Badge><Badge variant="secondary">Scopus</Badge></div>
          <h3 className="mt-3 font-display text-xl font-semibold">Optimal sizing of a hybrid PV-diesel-battery mini-grid for a village in Nigeria</h3>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            A hybrid <mark className="kw-include">solar</mark> PV-diesel-battery <mark className="kw-include">mini-grid</mark> is sized for a village of 450 households. The <mark className="kw-include">techno-economic</mark> optimisation yields an <mark className="kw-include">LCOE</mark> of 0.31 USD/kWh and a renewable fraction of 78 %, outperforming diesel-only supply and <mark className="kw-exclude">grid extension</mark> beyond 12 km.
          </p>
          <div className="mt-4 rounded-lg border border-conflict/30 bg-conflict-bg px-3 py-2 text-xs text-conflict">AI suggests <b>include</b> (91 %) — cost outcomes for a solar mini-grid in sub-Saharan Africa.</div>
          <div className="mt-4 flex gap-2">
            <span className="rounded-md bg-include px-3 py-1.5 text-sm font-medium text-white">Include</span>
            <span className="rounded-md border border-maybe/40 bg-maybe-bg px-3 py-1.5 text-sm font-medium text-maybe">Maybe</span>
            <span className="rounded-md border border-exclude/40 bg-exclude-bg px-3 py-1.5 text-sm font-medium text-exclude">Exclude</span>
          </div>
        </div>
      </div>
    </div>
  );
}
