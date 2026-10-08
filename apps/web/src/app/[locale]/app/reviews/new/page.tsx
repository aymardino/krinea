"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useRouter } from "@/i18n/navigation";
import { api, ApiError, type Review } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader } from "@/components/ui/misc";

export default function NewReviewPage() {
  const t = useTranslations("reviews");
  const c = useTranslations("common");
  const router = useRouter();
  const qc = useQueryClient();
  const [form, setForm] = useState({ title: "", question: "", description: "", review_type: "systematic" });
  const [busy, setBusy] = useState(false);
  const types = ["systematic", "scoping", "rapid", "umbrella", "other"] as const;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post<Review>("/reviews", form);
      qc.invalidateQueries({ queryKey: ["reviews"] });
      router.push(`/app/reviews/${r.id}/data`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : c("error"));
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <PageHeader title={t("createTitle")} description={t("createText")} />
      <form onSubmit={submit} className="space-y-5 rounded-xl border border-border bg-card p-6 shadow-card">
        <div className="space-y-1.5"><Label htmlFor="title">{t("fields.title")}</Label><Input id="title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
        <div className="space-y-1.5"><Label htmlFor="question">{t("fields.question")}</Label><Textarea id="question" value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} /></div>
        <div className="space-y-1.5">
          <Label>{t("fields.type")}</Label>
          <Select value={form.review_type} onValueChange={(v) => setForm({ ...form, review_type: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{types.map((k) => <SelectItem key={k} value={k}>{t(`types.${k}`)}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5"><Label htmlFor="desc">{t("fields.description")}</Label><Textarea id="desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={() => router.back()}>{c("cancel")}</Button><Button type="submit" disabled={busy || !form.title.trim()}>{t("create")}</Button></div>
      </form>
    </div>
  );
}
