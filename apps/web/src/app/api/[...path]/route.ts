/**
 * Same-origin proxy to the Krinea API (decision D-23).
 *
 * The browser only ever talks to this web app: `/api/<path>` is forwarded to the API
 * (`API_URL`, an internal address in production) and the response, cookies included,
 * is streamed back. One public origin means first-party session cookies, no CORS,
 * one domain to configure. The API learns the public origin from the header we add
 * (`x-krinea-origin`) and trusts it because `PROXY_KEY` equals its `SECRET_KEY`.
 * That origin is configuration, never client input: forwarded headers can be forged.
 */
import type { NextRequest } from "next/server";

import { SITE_URL } from "@/lib/site";
import { upstreamUrl } from "@/lib/upstream";

export const dynamic = "force-dynamic";


// Headers that belong to one hop only, or that fetch sets itself
const HOP = new Set([
  "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "host",
  "content-length", "content-encoding", "proxy-authorization", "proxy-authenticate", "expect",
]);
// Client-supplied forwarding headers are not passed on: anyone can forge them, and the API
// learns the public origin from x-krinea-origin only.
const FORGEABLE = new Set(["x-forwarded-host", "x-forwarded-proto", "x-forwarded-port", "forwarded", "x-krinea-internal"]);
const BUFFER_LIMIT = 2 * 1024 * 1024;        // bodies up to 2 MB are buffered so a request can be retried
const RETRY_DELAYS_MS = [500, 1000, 2000, 4000];   // ~7.5 s of connection errors (API restarting, cold start)
const TIMEOUT_MS = 20_000;                   // per attempt, buffered requests
const STREAM_TIMEOUT_MS = 10 * 60_000;       // streamed uploads
const RETRYABLE = new Set(["ECONNREFUSED", "ECONNRESET", "ENOTFOUND", "EAI_AGAIN", "ETIMEDOUT", "EHOSTUNREACH", "ENETUNREACH",
  "UND_ERR_SOCKET", "UND_ERR_CONNECT_TIMEOUT"]);

/**
 * Public origin of the site, used by the API to build links in e-mails and OAuth redirects.
 * In production it is configuration only: PUBLIC_ORIGIN (run time), else NEXT_PUBLIC_SITE_URL
 * (build time, default https://krinea.org). X-Forwarded-Host/Proto are never trusted, since any
 * client can set them. Only in development is the Host header used, so localhost works as is.
 */
function publicOrigin(req: NextRequest): string {
  if (process.env.NODE_ENV === "production") {
    return (process.env.PUBLIC_ORIGIN || process.env.NEXT_PUBLIC_SITE_URL || SITE_URL).trim().replace(/\/+$/, "");
  }
  return `http://${req.headers.get("host") || "localhost:3000"}`;
}

function errorCode(err: unknown): string {
  const e = err as { name?: string; message?: string; cause?: { code?: string; message?: string; errors?: { code?: string }[] } };
  if (e?.name === "TimeoutError" || e?.name === "AbortError") return "ETIMEDOUT";
  const cause = e?.cause;
  return cause?.code || cause?.errors?.find((x) => x?.code)?.code || cause?.message || e?.message || String(err);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const base = upstreamUrl(process.env.API_URL);
  const target = `${base}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP.has(key) && !FORGEABLE.has(key)) headers.set(key, value);
  });
  headers.set("x-krinea-origin", publicOrigin(req));
  headers.set("x-krinea-proxy-key", process.env.PROXY_KEY ?? process.env.SECRET_KEY ?? "dev-secret-change-me");

  // Small bodies are buffered (retryable); large ones (PDF uploads) are streamed once.
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const declared = Number(req.headers.get("content-length") ?? "0");
  let body: BodyInit | null = null;
  let retryable = true;
  if (hasBody) {
    if (declared && declared <= BUFFER_LIMIT) body = await req.arrayBuffer();
    else { body = req.body; retryable = false; }
  }

  let lastError: unknown;
  for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt++) {
    try {
      const res = await fetch(target, {
        method: req.method,
        headers,
        body,
        redirect: "manual",
        cache: "no-store",
        signal: AbortSignal.timeout(retryable ? TIMEOUT_MS : STREAM_TIMEOUT_MS),
        ...({ duplex: "half" } as Record<string, unknown>),   // Node needs this to stream a request body
      });
      const out = new Headers();
      res.headers.forEach((value, key) => {
        if (!HOP.has(key) && key !== "set-cookie") out.set(key, value);
      });
      for (const cookie of res.headers.getSetCookie()) out.append("set-cookie", cookie);
      return new Response(res.status === 204 || res.status === 304 ? null : res.body, {
        status: res.status,
        statusText: res.statusText,
        headers: out,
      });
    } catch (err) {
      lastError = err;
      const code = errorCode(err);
      console.error(`[api proxy] ${req.method} ${target} -> ${code}${attempt < RETRY_DELAYS_MS.length && retryable ? " (retrying)" : ""}`);
      if (!retryable || !RETRYABLE.has(code) || attempt === RETRY_DELAYS_MS.length) break;
      await sleep(RETRY_DELAYS_MS[attempt]);
    }
  }
  const code = errorCode(lastError);
  return Response.json(
    { detail: "The API is not reachable", target: new URL(base).host, code },
    { status: RETRYABLE.has(code) ? 503 : 502, headers: { "retry-after": "10" } },
  );
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as HEAD, proxy as OPTIONS };
