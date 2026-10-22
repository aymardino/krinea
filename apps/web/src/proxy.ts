import createMiddleware from "next-intl/middleware";
import type { NextFetchEvent, NextRequest } from "next/server";
import { recordPageView } from "@/lib/audience";
import { routing } from "./i18n/routing";

const intl = createMiddleware(routing);

/** Locale routing (next-intl), plus the cookie-free audience count of the public pages: the
 *  report is sent after the response has gone out and never delays it. Redirects (for
 *  example "/" to "/en") are not counted, only the page that is finally served. */
export default async function proxy(request: NextRequest, event: NextFetchEvent) {
  const response = await intl(request);
  if (response.status === 200) {
    const report = recordPageView(request, routing.defaultLocale);
    if (report) event.waitUntil(report);
  }
  return response;
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
