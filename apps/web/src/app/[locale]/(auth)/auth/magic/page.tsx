"use client";

import { useEffect, useState } from "react";
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
  useEffect(() => {
    const token = params.get("token");
    if (!token) return setFailed(true);
    api.post("/auth/magic-link/verify", { token })
      .then(async () => { await qc.invalidateQueries({ queryKey: ["me"] }); router.replace("/app"); })
      .catch(() => setFailed(true));
  }, [params, router, qc]);
  return (
    <div className="text-center">
      <p className="text-sm text-muted-foreground">{failed ? t("magicInvalid") : t("magicChecking")}</p>
      {failed && <Link href="/sign-in" className="mt-4 inline-block text-primary underline">{t("noAccount")}</Link>}
    </div>
  );
}
