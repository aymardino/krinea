"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/misc";

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.7-2.4 3.6v3h3.9c2.2-2.1 3.5-5.1 3.5-8.8z" />
      <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3c-1.1.7-2.5 1.2-4.1 1.2-3.1 0-5.8-2.1-6.7-5H1.3v3.1C3.3 21.3 7.3 24 12 24z" />
      <path fill="#FBBC05" d="M5.3 14.3c-.3-.7-.4-1.5-.4-2.3s.1-1.6.4-2.3V6.6H1.3C.5 8.2 0 10 0 12s.5 3.8 1.3 5.4l4-3.1z" />
      <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4C18 1.2 15.2 0 12 0 7.3 0 3.3 2.7 1.3 6.6l4 3.1c.9-2.9 3.6-4.9 6.7-4.9z" />
    </svg>
  );
}

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
  const params = useSearchParams();
  const providers = useQuery<{ google: boolean; email?: boolean }>({ queryKey: ["providers"], queryFn: () => api.get("/auth/providers"), staleTime: 300_000 });
  useEffect(() => { if (params.get("error") === "google") toast.error(t("googleError")); }, [params, t]);

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
      {providers.data?.google && (
        <>
          <Button type="button" variant="outline" className="mt-6 w-full" asChild>
            <a href={api.url(`/auth/google/start?next=${encodeURIComponent(next)}&locale=${locale}`)}><GoogleMark />{t("google")}</a>
          </Button>
          <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground"><Separator className="flex-1" />{t("or")}<Separator className="flex-1" /></div>
        </>
      )}
      <form onSubmit={submit} className={providers.data?.google ? "space-y-4" : "mt-6 space-y-4"}>
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
        {mode === "sign-up" && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t.rich("consent", {
              terms: (chunks) => <Link href="/terms" className="underline underline-offset-2 hover:text-foreground">{chunks}</Link>,
              privacy: (chunks) => <Link href="/privacy" className="underline underline-offset-2 hover:text-foreground">{chunks}</Link>,
            })}
          </p>
        )}
      </form>
      {providers.data?.email !== false && (<>
      <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground"><Separator className="flex-1" />{t("magicTitle")}<Separator className="flex-1" /></div>
      {magicSent === null ? (
        <Button type="button" variant="outline" className="w-full" disabled={busy || !email} onClick={magic}>{t("magicButton")}</Button>
      ) : (
        <p className="rounded-md bg-include-bg px-3 py-2 text-sm text-include">
          {t("magicSent")}
          {magicSent && <> <a className="underline" href={magicSent}>(dev link)</a></>}
          {" "}<button type="button" className="underline" onClick={() => setMagicSent(null)}>{t("magicAgain")}</button>
        </p>
      )}
      </>)}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        {mode === "sign-in" ? t("noAccount") : t("haveAccount")}{" "}
        <Link href={mode === "sign-in" ? "/sign-up" : "/sign-in"} className="font-medium text-primary underline-offset-4 hover:underline">{mode === "sign-in" ? c("signUp") : c("signIn")}</Link>
      </p>
    </div>
  );
}
