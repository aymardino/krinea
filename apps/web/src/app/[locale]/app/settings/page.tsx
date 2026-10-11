"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type Usage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader, Progress } from "@/components/ui/misc";

type KeyRow = { provider: string; masked: string; created_at: string };
const PROVIDERS = [["claude", "Anthropic (Claude)"], ["gemini", "Google (Gemini)"], ["deepseek", "DeepSeek"]] as const;

export default function UserSettingsPage() {
  const t = useTranslations("userSettings");
  const c = useTranslations("common");
  const qc = useQueryClient();
  const { data: me } = useMe();
  const keys = useQuery<KeyRow[]>({ queryKey: ["keys"], queryFn: () => api.get("/auth/keys") });
  const usage = useQuery<Usage>({ queryKey: ["usage"], queryFn: () => api.get("/auth/usage") });
  const [name, setName] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : c("error"));

  const profile = useMutation({
    mutationFn: () => api.patch("/auth/me", { name: name ?? me?.name, password: password || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me"] }); setPassword(""); toast.success(c("saved")); },
    onError,
  });
  const saveKey = useMutation({
    mutationFn: (p: string) => api.put(`/auth/keys/${p}`, { key: draft[p] }),
    onSuccess: (_d, p) => { qc.invalidateQueries({ queryKey: ["keys"] }); setDraft((d) => ({ ...d, [p]: "" })); toast.success(c("saved")); },
    onError,
  });
  const removeKey = useMutation({ mutationFn: (p: string) => api.delete(`/auth/keys/${p}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["keys"] }), onError });
  const have = new Map((keys.data ?? []).map((k) => [k.provider, k]));
  const u = usage.data;

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("title")} />
      <Card>
        <CardHeader><CardTitle>{t("profile")}</CardTitle><CardDescription>{me?.email} · <Badge variant="brand">{t("plan")}: {me?.plan}</Badge></CardDescription></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5"><Label>{c("settings") === "" ? "" : "Name"}</Label><Input value={name ?? me?.name ?? ""} onChange={(e) => setName(e.target.value)} /></div>
          <div className="space-y-1.5"><Label>{t("newPassword")}</Label><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} autoComplete="new-password" /></div>
          <div className="sm:col-span-2"><Button onClick={() => profile.mutate()} disabled={profile.isPending}>{c("save")}</Button></div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{t("aiKeys")}</CardTitle><CardDescription>{t("aiKeysText")}</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          {PROVIDERS.map(([p, label]) => {
            const k = have.get(p);
            return (
              <div key={p} className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3">
                <div className="w-44 text-sm font-medium">{label}</div>
                {k ? (
                  <><code className="rounded bg-muted px-2 py-1 text-xs">{k.masked}</code><Button size="sm" variant="ghost" onClick={() => removeKey.mutate(p)}>{t("removeKey")}</Button></>
                ) : (
                  <><Input className="max-w-xs" type="password" placeholder="sk-…" value={draft[p] ?? ""} onChange={(e) => setDraft({ ...draft, [p]: e.target.value })} /><Button size="sm" disabled={!(draft[p] ?? "").trim() || saveKey.isPending} onClick={() => saveKey.mutate(p)}>{t("addKey")}</Button></>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
      {u && (
        <Card>
          <CardHeader><CardTitle>{t("usage")}</CardTitle><CardDescription>{u.month}</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between text-sm"><span>{t("included")}</span><span className="tabular-nums text-muted-foreground">{t("tokens", { n: u.included_used.toLocaleString() })} / {u.included_budget.toLocaleString()}</span></div>
              <Progress className="mt-2" value={u.included_budget ? Math.min(100, Math.round((u.included_used / u.included_budget) * 100)) : 0} tone="amber" />
            </div>
            <div className="flex justify-between text-sm"><span>{t("ownKey")}</span><span className="tabular-nums text-muted-foreground">{t("tokens", { n: u.own_key_tokens.toLocaleString() })}</span></div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
