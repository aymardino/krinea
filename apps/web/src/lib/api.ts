/** Thin typed client for the Krinea API. Cookies carry the session (credentials: include).
 *  By default the browser goes through this app's own `/api` proxy (D-23): same origin, no CORS,
 *  no build-time URL. Set NEXT_PUBLIC_API_URL only to call a separately hosted API directly. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = text;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? (data as { detail: unknown }).detail
        : text;
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  url: (path: string) => `${API_URL}${path}`,
};

// ── Types mirroring krinea_api.schemas ─────────────────────────────────────────
export type User = { id: string; email: string; name: string; locale: string; plan: string; created_at: string; email_verified: boolean };
export type Member = { user_id: string; email: string; name: string; role: string; created_at: string };
export type Invitation = { id: string; email: string; role: string; created_at: string; expires_at: string; accepted_at: string | null; accept_url: string | null };
export type ReviewSummary = { id: string; title: string; review_type: string; my_role: string; is_archived: boolean; updated_at: string; n_records: number; n_members: number; progress: number };
export type StageStats = { pool: number; pending: number; include: number; maybe: number; exclude: number; conflict: number; my_done: number; my_left: number; my_seconds: number; reviewers: { user_id: string; name: string; email: string; role: string; done: number; left: number; seconds: number; include: number; maybe: number; exclude: number }[] };
export type Summary = { records: number; duplicates: number; unique: number; required_reviewers: number; stages: { ta: StageStats; ft: StageStats }; extraction: { pool: number; draft?: number; verified?: number; failed?: number }; pdfs: { available: number; not_retrieved: number } };
export type Criteria = { question: string; inclusion: string; exclusion: string; exclusion_reasons: string[]; highlight_include: string[]; highlight_exclude: string[]; required_reviewers: number };
export type Settings = { required_reviewers: number; blind: boolean; ai_provider: string; ai_model_screening: string; ai_model_extraction: string };
export type Field = { name: string; label: string; kind: string; options: string[]; hint: string; required: boolean };
export type Review = { id: string; title: string; description: string; question: string; review_type: string; criteria: Criteria; settings: Settings; extraction_schema: Field[]; is_archived: boolean; created_at: string; updated_at: string; my_role: string; members: Member[]; counts: Summary };
export type Decision = { reviewer: string; name: string; decision: string; reason: string; note: string; decided_at: string };
export type AISuggestion = { decision: string; reason: string; rationale: string; confidence: number; model: string };
export type StudyRecord = { id: number; title: string; abstract: string; authors: string; year: string; journal: string; volume: string; issue: string; pages: string; doi: string; url: string; keywords: string; pmid: string; type: string; language: string; source_db: string; import_id: string | null; is_duplicate: boolean; duplicate_of: number | null; dup_score: number | null; dup_reason: string; pdf_status: string; has_pdf: boolean; labels: string; notes: string; ta_status: string; ft_status: string; my_decision: Decision | null; decisions: Decision[]; ai: AISuggestion | null };
export type RecordPage = { items: StudyRecord[]; total: number; next_cursor: number | null };
export type ImportRow = { id: string; filename: string; format: string; source_db: string; n_records: number; n_skipped: number; n_duplicates: number; created_at: string; error?: string };
export type Candidate = { id: number; score: number; reason: string; status: string; a: StudyRecord; b: StudyRecord };
export type Duplicate = { id: number; title: string; year: string; doi: string; source_db: string; score: number; reason: string; kept_id: number; kept_title: string };
export type Job = { id: string; kind: string; status: string; progress: number; result: { [k: string]: unknown }; error: string; created_at: string; finished_at: string | null };
export type Extraction = { record_id: number; status: string; model: string; values: { [k: string]: string }; quotes: { [k: string]: string }; ai_values: { [k: string]: string }; text_extracted: string; error: string; created_at: string; verified_at: string | null; flags: { [k: string]: [string, string] } };
export type Prisma = { identified: number; by_source: { [k: string]: number }; duplicates_removed: number; screened: number; ta_excluded: number; ta_pending: number; sought: number; not_retrieved: number; assessed: number; ft_excluded: number; ft_excluded_reasons: { [k: string]: number }; ft_pending: number; included: number; reports_included: number };
export type Usage = { month: string; included_budget: number; included_used: number; own_key_tokens: number };
export type KeywordCounts = { include: { keyword: string; n: number }[]; exclude: { keyword: string; n: number }[] };
export type Activity = { items: { kind: string; detail: { [k: string]: unknown }; at: string; user: string }[]; throughput: { day: string; [k: string]: number | string }[] };
