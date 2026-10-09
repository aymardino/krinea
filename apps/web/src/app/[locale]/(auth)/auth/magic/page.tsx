"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

export default function MagicPage() {
  const t = useTranslations("auth");
  const params = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();
  const [failed, setFailed] = useState(false);
  const started = useRef(false);           // the token is single-use: verify exactly once
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = params.get("token");
    const done = async () => { await qc.invalidateQueries({ queryKey: ["me"] }); router.replace("/app"); };
    if (!token) return setFailed(true);
    api.post("/auth/magic-link/verify", { token })
      .then(done)
      .catch(async () => {
        // A used link while the session from its first use is still valid: just go in.
        try { await api.get("/auth/me"); await done(); } catch { setFailed(true); }
      });
  }, [params, router, qc]);
  return (
    <div className="text-center">
      <p className="text-sm text-muted-foreground">{failed ? t("magicInvalid") : t("magicChecking")}</p>
      {failed && <Link href="/sign-in" className="mt-4 inline-block text-primary underline">{t("noAccount")}</Link>}
    </div>
  );
}
