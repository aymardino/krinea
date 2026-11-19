"use client";

import { useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, Sparkles } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { api, ApiError, type Job, type Review, type Usage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const PROVIDER_NAMES: { [k: string]: string } = { claude: "Anthropic Claude", gemini: "Google Gemini", deepseek: "DeepSeek" };
type KeyRow = { provider: string; masked: string; created_at: string };
/** What an AI screening job reports (services/jobs.py); runs made before kinds existed only
 *  have ok, total and errors. */
export type AiRunResult = { ok?: number; failed?: number; total?: number; provider?: string; model?: string; error_kind?: string; error?: string; errors?: string[]; stopped?: boolean };
const ERROR_KINDS = ["nokey", "key", "model", "quota", "credit", "output", "other"];

/** What went wrong in an AI run, in words the reviewer can act on, or "" when nothing did. */
export function aiErrorKind(job: Job): string {
  const r = job.result as AiRunResult;
  if (job.status === "failed") return "failed";
  if (r.error_kind) return ERROR_KINDS.includes(r.error_kind) ? r.error_kind : "other";
  return r.errors?.length ? "other" : "";
}

/** The outcome of the reviewer's last AI run, kept in the panel once the run is over: how
 *  many suggestions were saved, with which model, and when something went wrong, what it
 *  means and what to do, with the provider's own message underneath. */
export function AiRunSummary({ job, provider }: { job: Job; provider: string }) {
  const t = useTranslations("review.screening");
  const r = job.result as AiRunResult;
  const name = PROVIDER_NAMES[r.provider || provider] ?? r.provider ?? provider;
  const kind = aiErrorKind(job);
  const detail = job.status === "failed" ? job.error : r.error || (r.errors ?? []).slice(-1)[0] || "";
  return (
    <div className="space-y-1.5 text-[11px] leading-snug text-muted-foreground">
      <p>{t("aiLast", { ok: Number(r.ok ?? 0), total: Number(r.total ?? 0) })}{r.model && <> {t("aiLastModel", { model: r.model })}</>}</p>
      {kind && <p className="text-exclude">{kind === "failed" ? t("aiFailed") : t(`aiError.${kind}`, { provider: name, model: r.model || "?" })}</p>}
      {detail && (
        <details>
          <summary className="cursor-pointer select-none hover:text-foreground">{t("aiErrorDetail")}</summary>
          <p className="mt-1 break-words font-mono text-[10px]">{detail}</p>
        </details>
      )}
    </div>
  );
}

/** The AI panel of the screening rail: run suggestions, and add the provider key
 *  right here when none is on file (instead of going to the user settings). `status` shows
 *  the run under way, or how the last one went. */
export function AiCard({ review, onRun, running, label, hint, status }: { review: Review; onRun: () => void; running: boolean; label: string; hint?: string; status?: ReactNode }) {
  const t = useTranslations("review.screening");
  const c = useTranslations("common");
  const qc = useQueryClient();
  const provider = review.settings.ai_provider || "claude";
  const name = PROVIDER_NAMES[provider] ?? provider;
  const keys = useQuery<KeyRow[]>({ queryKey: ["keys"], queryFn: () => api.get("/auth/keys") });
  const usage = useQuery<Usage>({ queryKey: ["usage"], queryFn: () => api.get("/auth/usage") });
  const mine = keys.data?.find((k) => k.provider === provider);
  const creditsLeft = usage.data ? Math.max(0, usage.data.included_budget - usage.data.included_used) : 0;
  const ready = !!mine || creditsLeft > 0;
  const [draft, setDraft] = useState("");
  const saveKey = useMutation({
    mutationFn: () => api.put(`/auth/keys/${provider}`, { key: draft.trim() }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["keys"] }); setDraft(""); toast.success(t("aiKeySaved")); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : c("error")),
  });
  const removeKey = useMutation({
    mutationFn: () => api.delete(`/auth/keys/${provider}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keys"] }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : c("error")),
  });

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Sparkles className="size-3.5" />AI</p>
      <p className="mt-2 flex items-baseline justify-between gap-2 text-xs text-muted-foreground"><span className="truncate">{t("aiProvider")} <span className="font-medium text-foreground">{name}</span></span><Link href={`/app/reviews/${review.id}/settings`} className="shrink-0 underline-offset-2 hover:underline">{t("aiChange")}</Link></p>
      {keys.isSuccess && (mine ? (
        <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground"><KeyRound className="size-3.5 text-include" /><code className="rounded bg-muted px-1.5 py-0.5">{mine.masked}</code><button type="button" className="hover:underline" onClick={() => removeKey.mutate()} disabled={removeKey.isPending}>{t("aiRemoveKey")}</button></p>
      ) : creditsLeft > 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">{t("aiCredits", { n: creditsLeft.toLocaleString() })}</p>
      ) : (
        <form className="mt-3 space-y-2" onSubmit={(e) => { e.preventDefault(); if (draft.trim().length >= 8) saveKey.mutate(); }}>
          <p className="text-xs text-muted-foreground">{t("aiNoKey", { provider: name })}</p>
          <Input type="password" autoComplete="off" className="h-8 text-xs" placeholder={t("aiKeyPlaceholder")} value={draft} onChange={(e) => setDraft(e.target.value)} />
          <Button type="submit" size="sm" className="w-full" disabled={draft.trim().length < 8 || saveKey.isPending}>{t("aiKeySave")}</Button>
          <p className="text-[11px] text-muted-foreground">{t("aiKeyStored")} <Link href="/security" target="_blank" className="underline underline-offset-2 hover:text-foreground">{t("aiKeyMore")}</Link></p>
        </form>
      ))}
      <Button className="mt-3 w-full" size="sm" variant={ready ? "default" : "outline"} onClick={onRun} disabled={running || (keys.isSuccess && !ready)}>{label}</Button>
      {hint && <p className="mt-1.5 text-[11px] text-muted-foreground">{hint}</p>}
      {status && <div className="mt-3 border-t border-border pt-3">{status}</div>}
    </div>
  );
}
