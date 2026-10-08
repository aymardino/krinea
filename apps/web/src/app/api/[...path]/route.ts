/**
 * Same-origin proxy to the Tamis API (decision D-23).
 *
 * The browser only ever talks to this web app: `/api/<path>` is forwarded to the API
 * (`API_URL`, an internal address in production) and the response, cookies included,
 * is streamed back. One public origin means first-party session cookies, no CORS,
 * one domain to configure. The API learns the public origin from the headers we add
 * and trusts them because `PROXY_KEY` equals its `SECRET_KEY`.
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function upstream(): string {
  const raw = (process.env.API_URL ?? "http://localhost:8000").trim().replace(/\/+$/, "");
  return /^https?:\/\//.test(raw) ? raw : `http://${raw}`;
}

// Headers that belong to one hop only, or that fetch sets itself
const HOP = new Set([
  "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "host",
  "content-length", "content-encoding", "proxy-authorization", "proxy-authenticate", "expect",
]);

function publicOrigin(req: NextRequest): string {
  const proto = req.headers.get("x-forwarded-proto")?.split(",")[0].trim() || "http";
  const host = req.headers.get("x-forwarded-host")?.split(",")[0].trim() || req.headers.get("host") || "localhost:3000";
  return `${proto}://${host}`;
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const target = `${upstream()}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP.has(key)) headers.set(key, value);
  });
  headers.set("x-tamis-origin", publicOrigin(req));
  headers.set("x-tamis-proxy-key", process.env.PROXY_KEY ?? process.env.SECRET_KEY ?? "dev-secret-change-me");
  headers.set("x-forwarded-host", req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "");

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let res: Response;
  try {
    res = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      redirect: "manual",
      cache: "no-store",
      // Node needs this to stream a request body
      ...({ duplex: "half" } as Record<string, unknown>),
    });
  } catch (err) {
    console.error(`[api proxy] ${req.method} ${target}:`, err);
    return Response.json({ detail: "The API is not reachable" }, { status: 502 });
  }

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
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as HEAD, proxy as OPTIONS };
