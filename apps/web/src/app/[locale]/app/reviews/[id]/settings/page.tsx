"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2, UserPlus, X } from "lucide-react";
import { useRouter } from "@/i18n/navigation";
import { api, ApiError, type Criteria, type Field, type Invitation, type Member, type Review } from "@/lib/api";
import { canEdit, useReview } from "@/components/app/review-context";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch, Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Avatar, PageHeader } from "@/components/ui/misc";

const KINDS = ["text", "sentences", "number", "year", "yesno", "enum", "multi", "list"];
const PROVIDERS = ["claude", "gemini", "deepseek"];

export default function SettingsPage() {
  const t = useTranslations("review.settings");
  const c = useTranslations("common");
  const qc = useQueryClient();
  const router = useRouter();
  const { review, refresh } = useReview();
  const rid = review.id;
  const editable = canEdit(review.my_role);
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : c("error"));

  const [general, setGeneral] = useState({ title: review.title, question: review.question, description: review.description });
  const [crit, setCrit] = useState({
    inclusion: review.criteria.inclusion, exclusion: review.criteria.exclusion,
    reasons: review.criteria.exclusion_reasons.join("\n"),
    inc: review.criteria.highlight_include.join(", "), exc: review.criteria.highlight_exclude.join(", "),
  });
  const [settings, setSettings] = useState({ ...review.settings });
  const [fields, setFields] = useState<Field[]>(review.extraction_schema);
  const [invite, setInvite] = useState({ email: "", role: "reviewer" });
  const [confirmTitle, setConfirmTitle] = useState("");

  const invitations = useQuery<Invitation[]>({ queryKey: ["invitations", rid], queryFn: () => api.get(`/reviews/${rid}/invitations`), enabled: editable });
  const templates = useQuery<{ default: Field[]; energy?: Field[] }>({ queryKey: ["templates"], queryFn: () => api.get("/reviews/templates/extraction") });

  const patch = useMutation({
    mutationFn: (body: Omit<Partial<Review>, "criteria"> & { criteria?: Partial<Criteria> }) => api.patch<Review>(`/reviews/${rid}`, body),
    onSuccess: (r) => { qc.setQueryData(["review", rid], r); refresh(); toast.success(c("saved")); },
    onError,
  });
  const sendInvite = useMutation({
    mutationFn: () => api.post<Invitation>(`/reviews/${rid}/invitations`, invite),
    onSuccess: (inv) => { qc.invalidateQueries({ queryKey: ["invitations", rid] }); setInvite({ email: "", role: "reviewer" }); toast.success(inv.accept_url ? `Dev link: ${inv.accept_url}` : c("saved")); },
    onError,
  });
  const revoke = useMutation({ mutationFn: (id: string) => api.delete(`/reviews/${rid}/invitations/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["invitations", rid] }), onError });
  const setRole = useMutation({ mutationFn: ({ uid, role }: { uid: string; role: string }) => api.patch<Member[]>(`/reviews/${rid}/members/${uid}`, { role }), onSuccess: refresh, onError });
  const removeMember = useMutation({ mutationFn: (uid: string) => api.delete<Member[]>(`/reviews/${rid}/members/${uid}`), onSuccess: refresh, onError });
  const destroy = useMutation({ mutationFn: () => api.delete(`/reviews/${rid}`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["reviews"] }); router.push("/app"); }, onError });

  const updateField = (i: number, k: keyof Field, v: string | boolean | string[]) => setFields(fields.map((f, j) => (j === i ? { ...f, [k]: v } : f)));
  const parseList = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} />

      <Card>
        <CardHeader><CardTitle>{t("general")}</CardTitle></CardHeader>
        <CardContent className="grid gap-4">
          <div className="space-y-1.5"><Label>Title</Label><Input value={general.title} onChange={(e) => setGeneral({ ...general, title: e.target.value })} disabled={!editable} /></div>
          <div className="space-y-1.5"><Label>Research question</Label><Textarea value={general.question} onChange={(e) => setGeneral({ ...general, question: e.target.value })} disabled={!editable} /></div>
          <div className="space-y-1.5"><Label>Description</Label><Textarea value={general.description} onChange={(e) => setGeneral({ ...general, description: e.target.value })} disabled={!editable} /></div>
          {editable && <div><Button onClick={() => patch.mutate(general)} disabled={patch.isPending}>{c("save")}</Button></div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("criteria")}</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5"><Label>{t("inclusion")}</Label><Textarea className="min-h-[120px]" value={crit.inclusion} onChange={(e) => setCrit({ ...crit, inclusion: e.target.value })} disabled={!editable} /></div>
          <div className="space-y-1.5"><Label>{t("exclusion")}</Label><Textarea className="min-h-[120px]" value={crit.exclusion} onChange={(e) => setCrit({ ...crit, exclusion: e.target.value })} disabled={!editable} /></div>
          <div className="space-y-1.5 md:col-span-2"><Label>{t("reasons")}</Label><Textarea className="min-h-[120px]" value={crit.reasons} onChange={(e) => setCrit({ ...crit, reasons: e.target.value })} disabled={!editable} /></div>
          <div className="space-y-1.5"><Label>{t("highlightInclude")}</Label><Input value={crit.inc} onChange={(e) => setCrit({ ...crit, inc: e.target.value })} disabled={!editable} /><p className="text-xs text-muted-foreground">{t("keywordHint")}</p></div>
          <div className="space-y-1.5"><Label>{t("highlightExclude")}</Label><Input value={crit.exc} onChange={(e) => setCrit({ ...crit, exc: e.target.value })} disabled={!editable} /></div>
          {editable && <div className="md:col-span-2"><Button onClick={() => patch.mutate({ criteria: { inclusion: crit.inclusion, exclusion: crit.exclusion, exclusion_reasons: crit.reasons.split("\n").map((s) => s.trim()).filter(Boolean), highlight_include: parseList(crit.inc), highlight_exclude: parseList(crit.exc) } })} disabled={patch.isPending}>{c("save")}</Button></div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("team")}</CardTitle><CardDescription>{t("blindHint")}</CardDescription></CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap items-end gap-6">
            <div className="space-y-1.5"><Label>{t("required")}</Label>
              <Select value={String(settings.required_reviewers)} onValueChange={(v) => setSettings({ ...settings, required_reviewers: Number(v) })} disabled={!editable}>
                <SelectTrigger className="w-24"><SelectValue /></SelectTrigger><SelectContent>{[1, 2, 3].map((n) => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={settings.blind} onCheckedChange={(v) => setSettings({ ...settings, blind: v })} disabled={!editable} />{t("blind")}</label>
            {editable && <Button variant="outline" onClick={() => patch.mutate({ settings })} disabled={patch.isPending}>{c("save")}</Button>}
          </div>
          <ul className="divide-y divide-border rounded-lg border border-border">
            {review.members.map((m) => (
              <li key={m.user_id} className="flex items-center gap-3 p-3 text-sm">
                <Avatar name={m.name || m.email} />
                <div className="min-w-0 flex-1"><p className="truncate font-medium">{m.name || m.email}</p><p className="truncate text-xs text-muted-foreground">{m.email}</p></div>
                {m.role === "owner" || !editable ? <Badge variant="secondary">{c(`role.${m.role}` as "role.owner")}</Badge> : (
                  <>
                    <Select value={m.role} onValueChange={(role) => setRole.mutate({ uid: m.user_id, role })}><SelectTrigger className="w-32"><SelectValue /></SelectTrigger><SelectContent>{["admin", "reviewer", "viewer"].map((r) => <SelectItem key={r} value={r}>{c(`role.${r}` as "role.admin")}</SelectItem>)}</SelectContent></Select>
                    <Button size="icon" variant="ghost" onClick={() => removeMember.mutate(m.user_id)}><X /></Button>
                  </>
                )}
              </li>
            ))}
          </ul>
          {editable && (
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1.5"><Label>{t("invite")}</Label><Input type="email" className="w-64" placeholder="name@university.edu" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} /></div>
              <div className="space-y-1.5"><Label>{t("inviteRole")}</Label><Select value={invite.role} onValueChange={(role) => setInvite({ ...invite, role })}><SelectTrigger className="w-32"><SelectValue /></SelectTrigger><SelectContent>{["admin", "reviewer", "viewer"].map((r) => <SelectItem key={r} value={r}>{c(`role.${r}` as "role.admin")}</SelectItem>)}</SelectContent></Select></div>
              <Button onClick={() => sendInvite.mutate()} disabled={!invite.email || sendInvite.isPending}><UserPlus />{t("invite")}</Button>
            </div>
          )}
          {!!invitations.data?.length && (
            <div><p className="mb-2 text-sm font-medium">{t("pending")}</p>
              <ul className="space-y-1 text-sm">{invitations.data.map((i) => <li key={i.id} className="flex items-center gap-2"><span>{i.email}</span><Badge variant="secondary">{i.role}</Badge><Button size="xs" variant="ghost" onClick={() => revoke.mutate(i.id)}><X /></Button></li>)}</ul>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("form")}</CardTitle><CardDescription>{t("formHint")}</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          <div className="hidden grid-cols-[1fr_1fr_120px_1fr_1.4fr_60px_32px] gap-2 text-xs font-medium text-muted-foreground md:grid">
            <span>{t("field.name")}</span><span>{t("field.label")}</span><span>{t("field.kind")}</span><span>{t("field.options")}</span><span>{t("field.hint")}</span><span>{t("field.required")}</span><span />
          </div>
          {fields.map((f, i) => (
            <div key={i} className="grid gap-2 rounded-lg border border-border p-2 md:grid-cols-[1fr_1fr_120px_1fr_1.4fr_60px_32px] md:border-0 md:p-0">
              <Input value={f.name} onChange={(e) => updateField(i, "name", e.target.value)} disabled={!editable} placeholder={t("field.name")} />
              <Input value={f.label} onChange={(e) => updateField(i, "label", e.target.value)} disabled={!editable} placeholder={t("field.label")} />
              <Select value={f.kind} onValueChange={(v) => updateField(i, "kind", v)} disabled={!editable}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{KINDS.map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}</SelectContent></Select>
              <Input value={f.options.join(" | ")} onChange={(e) => updateField(i, "options", e.target.value.split("|").map((s) => s.trim()).filter(Boolean))} disabled={!editable || !["enum", "multi"].includes(f.kind)} placeholder="a | b | c" />
              <Input value={f.hint} onChange={(e) => updateField(i, "hint", e.target.value)} disabled={!editable} placeholder={t("field.hint")} />
              <div className="flex items-center justify-center"><Checkbox checked={f.required} onCheckedChange={(v) => updateField(i, "required", !!v)} disabled={!editable} /></div>
              <Button size="icon" variant="ghost" disabled={!editable} onClick={() => setFields(fields.filter((_, j) => j !== i))}><Trash2 /></Button>
            </div>
          ))}
          {editable && (
            <div className="flex flex-wrap gap-2 pt-2">
              <Button variant="outline" onClick={() => setFields([...fields, { name: "", label: "", kind: "text", options: [], hint: "", required: false }])}><Plus />{t("addField")}</Button>
              <Button onClick={() => patch.mutate({ extraction_schema: fields })} disabled={patch.isPending}>{c("save")}</Button>
              <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">{t("templates")}:
                <Button size="xs" variant="ghost" onClick={() => templates.data && setFields(templates.data.default)}>{t("templateDefault")}</Button>
                {templates.data?.energy && <Button size="xs" variant="ghost" onClick={() => setFields(templates.data!.energy!)}>{t("templateEnergy")}</Button>}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("ai")}</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="space-y-1.5"><Label>{t("aiProvider")}</Label><Select value={settings.ai_provider} onValueChange={(v) => setSettings({ ...settings, ai_provider: v })} disabled={!editable}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{PROVIDERS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1.5"><Label>{t("aiModelScreening")}</Label><Input value={settings.ai_model_screening} onChange={(e) => setSettings({ ...settings, ai_model_screening: e.target.value })} disabled={!editable} placeholder="default" /></div>
          <div className="space-y-1.5"><Label>{t("aiModelExtraction")}</Label><Input value={settings.ai_model_extraction} onChange={(e) => setSettings({ ...settings, ai_model_extraction: e.target.value })} disabled={!editable} placeholder="default" /></div>
          {editable && <div className="md:col-span-3"><Button onClick={() => patch.mutate({ settings })} disabled={patch.isPending}>{c("save")}</Button></div>}
        </CardContent>
      </Card>

      {review.my_role === "owner" && (
        <Card className="border-exclude/40">
          <CardHeader><CardTitle className="text-exclude">{t("danger")}</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <Button variant="outline" onClick={() => patch.mutate({ is_archived: !review.is_archived })}>{t("archive")}</Button>
            <div className="space-y-1.5"><Label>{t("deleteConfirm")}</Label><Input className="w-72" value={confirmTitle} onChange={(e) => setConfirmTitle(e.target.value)} /></div>
            <Button variant="destructive" disabled={confirmTitle !== review.title || destroy.isPending} onClick={() => destroy.mutate()}><Trash2 />{t("deleteReview")}</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
