import type { NextRequest } from "next/server";
import { upstreamUrl } from "@/lib/upstream";

/** Public pages whose visits are counted (the API keeps the same list). */
const PUBLIC = new Set(["/", "/pricing", "/about", "/contact", "/security", "/privacy", "/terms", "/legal", "/sign-in", "/sign-up"]);
const LOCALES = new Set(["en", "fr"]);

/** Reports one full page load of a public page to the API (POST /stats/view), which stores
 *  the page, the day, the language, the referring domain and a daily fingerprint, never the
 *  IP address or the browser signature. Client-side navigations and prefetches carry the RSC
 *  headers and are skipped, as are non-GET requests and the application itself. Returns null
 *  when there is nothing to report; the caller lets the request outlive the response. */
export function recordPageView(req: NextRequest, defaultLocale: string): Promise<void> | null {
  if (process.env.AUDIENCE_STATS === "0" || req.method !== "GET") return null;
  if (req.headers.get("rsc") || req.headers.get("next-router-prefetch") || req.headers.get("purpose") === "prefetch") return null;
  const dest = req.headers.get("sec-fetch-dest");
  if (dest && dest !== "document") return null;
  const segments = req.nextUrl.pathname.split("/").filter(Boolean);
  const lang = LOCALES.has(segments[0] ?? "") ? (segments.shift() as string) : defaultLocale;
  const path = `/${segments.join("/")}`;
  if (!PUBLIC.has(path)) return null;
  const body = JSON.stringify({
    path,
    lang,
    referrer: req.headers.get("referer") ?? "",
    ua: req.headers.get("user-agent") ?? "",
    ip: (req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim(),
  });
  return fetch(`${upstreamUrl(process.env.API_URL)}/stats/view`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-krinea-internal": "1",
      "x-krinea-proxy-key": process.env.PROXY_KEY ?? process.env.SECRET_KEY ?? "dev-secret-change-me",
    },
    body,
    signal: AbortSignal.timeout(3000),
  }).then(
    () => undefined,
    () => undefined,
  );
}
