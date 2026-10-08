"use client";

import { use, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { Button } from "@/components/ui/button";

type Preview = { review_title: string; role: string; email: string; inviter: string };

export default function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const t = useTranslations("auth");
  const c = useTranslations("common");
  const router = useRouter();
  const { data: me, isLoading } = useMe();
  const [busy, setBusy] = useState(false);
  const preview = useQuery<Preview>({ queryKey: ["invite", token], queryFn: () => api.get(`/reviews/invitations/${token}/preview`), retry: false });
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (preview.error) setError(preview.error instanceof ApiError ? preview.error.message : c("error")); }, [preview.error, c]);

  async function accept() {
    setBusy(true);
    try {
      const r = await api.post<{ id: string }>("/reviews/invitations/accept", { token });
      router.push(`/app/reviews/${r.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : c("error"));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <p className="text-sm text-exclude">{error}</p>;
  if (!preview.data || isLoading) return <p className="text-sm text-muted-foreground">{c("loading")}</p>;
  const p = preview.data;
  const nextUrl = `/invite/${token}`;
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold">{t("inviteTitle")}</h1>
      <p className="mt-3 text-muted-foreground">{t("inviteText", { inviter: p.inviter, title: p.review_title, role: c(`role.${p.role}` as "role.reviewer") })}</p>
      {me ? (
        <Button className="mt-6 w-full" onClick={accept} disabled={busy}>{t("inviteAccept")}</Button>
      ) : (
        <div className="mt-6 space-y-3">
          <p className="text-sm">{t("inviteNeedAccount", { email: p.email })}</p>
          <Button className="w-full" asChild><Link href={{ pathname: "/sign-up", query: { next: nextUrl } }}>{c("signUp")}</Link></Button>
          <Button className="w-full" variant="outline" asChild><Link href={{ pathname: "/sign-in", query: { next: nextUrl } }}>{c("signIn")}</Link></Button>
        </div>
      )}
    </div>
  );
}
