"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/misc";

export function AuthForm({ mode, next = "/app" }: { mode: "sign-in" | "sign-up"; next?: string }) {
  const t = useTranslations("auth");
  const c = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [magicSent, setMagicSent] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "sign-up") await api.post("/auth/register", { email, password, name, locale });
      else await api.post("/auth/login", { email, password });
      await qc.invalidateQueries({ queryKey: ["me"] });
      router.push(next);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : c("error"));
    } finally {
      setBusy(false);
    }
  }

  async function magic() {
    if (!email) return;
    setBusy(true);
    try {
      const r = await api.post<{ ok: boolean; dev_link?: string }>("/auth/magic-link", { email, locale });
      setMagicSent(r.dev_link ?? "");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : c("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="font-display text-2xl font-semibold">{mode === "sign-in" ? t("signInTitle") : t("signUpTitle")}</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        {mode === "sign-up" && (
          <div className="space-y-1.5"><Label htmlFor="name">{t("name")}</Label><Input id="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>
        )}
        <div className="space-y-1.5"><Label htmlFor="email">{t("email")}</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
        <div className="space-y-1.5">
          <Label htmlFor="password">{t("password")}</Label>
          <Input id="password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "sign-up" ? "new-password" : "current-password"} />
          {mode === "sign-up" && <p className="text-xs text-muted-foreground">{t("passwordHint")}</p>}
        </div>
        <Button type="submit" className="w-full" disabled={busy}>{mode === "sign-in" ? c("signIn") : c("signUp")}</Button>
      </form>
      <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground"><Separator className="flex-1" />{t("magicTitle")}<Separator className="flex-1" /></div>
      {magicSent === null ? (
        <Button type="button" variant="outline" className="w-full" disabled={busy || !email} onClick={magic}>{t("magicButton")}</Button>
      ) : (
        <p className="rounded-md bg-include-bg px-3 py-2 text-sm text-include">
          {t("magicSent")}
          {magicSent && <> <a className="underline" href={magicSent}>(dev link)</a></>}
        </p>
      )}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        {mode === "sign-in" ? t("noAccount") : t("haveAccount")}{" "}
        <Link href={mode === "sign-in" ? "/sign-up" : "/sign-in"} className="font-medium text-primary underline-offset-4 hover:underline">{mode === "sign-in" ? c("signUp") : c("signIn")}</Link>
      </p>
    </div>
  );
}
