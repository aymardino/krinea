/** Public address of the site, for canonical URLs, the sitemap and social cards. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://krinea.org").replace(/\/+$/, "");
export const REPO_URL = "https://github.com/aymardino/systematic_review";
/** Public marketing routes (path without locale prefix). */
export const PUBLIC_ROUTES = ["", "/pricing", "/about", "/contact", "/security", "/privacy", "/terms", "/legal"] as const;
export const localePath = (locale: string, path: string) => (locale === "en" ? path || "/" : `/${locale}${path}`);
