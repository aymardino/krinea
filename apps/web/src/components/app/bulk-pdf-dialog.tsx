"use client";

import { useRef, useState, type ComponentProps } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { FileText, Upload } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/misc";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Candidate = { id: number; title: string; year: string; authors: string; has_pdf: boolean; score: number };
type MatchOut = { filename: string; record_id: number | null; how: string; candidates: Candidate[] };
type Row = {
  key: string; file: File; state: "reading" | "read" | "error" | "adding" | "added" | "failed";
  match?: MatchOut; choice: string; error?: string;
};

// The choice of a file left out (a select item cannot have an empty value).
const SKIP = "skip";
// How many PDFs are sent at the same time (the server reads them one at a time, D-56).
const AT_ONCE = 2;

/** Runs `work` on each item, `n` at a time. */
async function inTurn<T>(items: T[], n: number, work: (item: T) => Promise<void>): Promise<void> {
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
    while (next < items.length) await work(items[next++]);
  }));
}

/** Adds the PDFs of many studies at once (D-55). Each file is read by the API, which finds its
 *  study among those included at title and abstract by its DOI, its title or its file name;
 *  nothing is stored then. The reviewer checks the list, changes a study or leaves a file out,
 *  and the PDFs then go to their studies as a single PDF goes. A study already picked for one
 *  file cannot be picked for another, and a study that has a PDF is only replaced when chosen
 *  by hand. */
export function BulkPdfDialog({ reviewId, onDone, className, size = "sm" }: { reviewId: string; onDone: () => void; className?: string; size?: ComponentProps<typeof Button>["size"] }) {
  const t = useTranslations("review.bulkPdf");
  const c = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState<"" | "reading" | "adding">("");
  const input = useRef<HTMLInputElement>(null);
  const update = (key: string, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const message = (e: unknown) => (e instanceof ApiError ? e.message : c("error"));

  const read = async (files: File[]) => {
    if (!files.length) return;
    const stamp = Date.now();
    const fresh: Row[] = files.map((file, i) => ({ key: `${stamp}-${i}-${file.name}`, file, state: "reading" as const, choice: SKIP }));
    setRows((rs) => [...rs, ...fresh]);
    setBusy("reading");
    await inTurn(fresh, AT_ONCE, async (row) => {
      const form = new FormData();
      form.append("file", row.file);
      try {
        const m = await api.upload<MatchOut>(`/reviews/${reviewId}/pdfs/match`, form);
        // The study found is picked unless it has a PDF already or another file has it.
        setRows((rs) => {
          const taken = new Set(rs.filter((r) => r.key !== row.key).map((r) => r.choice));
          const found = m.candidates.find((x) => x.id === m.record_id);
          const choice = found && !found.has_pdf && !taken.has(String(found.id)) ? String(found.id) : SKIP;
          return rs.map((r) => (r.key === row.key ? { ...r, state: "read" as const, match: m, choice } : r));
        });
      } catch (e) {
        update(row.key, { state: "error", error: message(e) });
      }
    });
    setBusy("");
  };

  const chosen = rows.filter((r) => (r.state === "read" || r.state === "failed") && r.choice !== SKIP);
  const add = async () => {
    setBusy("adding");
    let ok = 0;
    await inTurn(chosen, AT_ONCE, async (row) => {
      update(row.key, { state: "adding", error: undefined });
      const form = new FormData();
      form.append("file", row.file);
      try {
        await api.upload(`/reviews/${reviewId}/records/${row.choice}/pdf`, form);
        ok += 1;
        update(row.key, { state: "added" });
      } catch (e) {
        update(row.key, { state: "failed", error: message(e) });
      }
    });
    setBusy("");
    if (ok) {
      toast.success(t("added", { n: ok }));
      onDone();
    }
  };

  const reading = rows.filter((r) => r.state === "reading").length;
  const status = (r: Row) => {
    if (r.state === "reading") return <span>{t("reading")}</span>;
    if (r.state === "adding") return <span>{t("adding")}</span>;
    if (r.state === "added") return <span className="text-include">{t("addedOne")}</span>;
    if (r.state === "error" || r.state === "failed") return <span className="text-exclude">{r.error}</span>;
    const picked = r.match?.candidates.find((x) => String(x.id) === r.choice);
    return (
      <>
        <span>{t(`how.${r.match?.record_id != null && r.match.how ? r.match.how : "none"}`)}</span>
        {picked?.has_pdf && <span className="block text-maybe">{t("replaces")}</span>}
      </>
    );
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (busy) return; setOpen(o); if (!o) setRows([]); }}>
      <Button size={size} variant="outline" className={className} onClick={() => setOpen(true)}><Upload />{t("open")}</Button>
      <DialogContent wide className="max-h-[90vh] grid-rows-[auto_minmax(0,1fr)_auto]">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("intro")}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 space-y-3 overflow-y-auto">
          <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (!busy) read(Array.from(e.dataTransfer.files)); }}
               className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            <input ref={input} type="file" multiple accept="application/pdf,.pdf" className="hidden"
                   onChange={(e) => { const files = Array.from(e.target.files ?? []); e.target.value = ""; read(files); }} />
            <Button size="sm" variant="outline" onClick={() => input.current?.click()} disabled={!!busy}><Upload />{t("pick")}</Button>
            <span>{t("drop")}</span>
          </div>
          {busy === "reading" && (
            <div className="space-y-1">
              <Progress value={rows.length ? Math.round(((rows.length - reading) / rows.length) * 100) : 0} aria-label={t("title")} />
              <p className="text-xs text-muted-foreground">{t("readingCount", { done: rows.length - reading, total: rows.length })}</p>
            </div>
          )}
          {rows.length > 0 && (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {rows.map((r) => (
                <li key={r.key} className="grid gap-2 p-2.5 text-sm sm:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)] sm:items-center">
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 font-medium"><FileText className="size-3.5 shrink-0 text-muted-foreground" /><span className="truncate" title={r.file.name}>{r.file.name}</span></p>
                    <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{status(r)}</p>
                  </div>
                  {r.match && (r.state === "read" || r.state === "failed") && (
                    <Select value={r.choice} onValueChange={(v) => update(r.key, { choice: v })} disabled={!!busy}>
                      <SelectTrigger aria-label={t("study")} className={cn(r.choice === SKIP && "text-muted-foreground")}><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {r.match.candidates.map((x) => (
                          <SelectItem key={x.id} value={String(x.id)} disabled={String(x.id) !== r.choice && chosen.some((o) => o.key !== r.key && o.choice === String(x.id))}>
                            {x.title || "(untitled)"}{x.year ? ` (${x.year})` : ""}{x.has_pdf ? ` · ${t("hasPdf")}` : ""}
                          </SelectItem>
                        ))}
                        <SelectItem value={SKIP} className="text-muted-foreground">{t("skip")}</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        <DialogFooter className="items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">{rows.length ? t("summary", { n: chosen.length }) : ""}</p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="ghost" onClick={() => { setOpen(false); setRows([]); }} disabled={!!busy}>{c("close")}</Button>
            <Button onClick={add} disabled={!!busy || !chosen.length}><Upload />{t("add", { n: chosen.length })}</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
