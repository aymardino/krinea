/** Public address of the site, for canonical URLs, the sitemap and social cards. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://krinea.org").replace(/\/+$/, "");
/** Source code repository (the only place this URL is defined). */
export const REPO_URL = "https://github.com/aymardino/krinea";
/** Released version of Krinea, shown in the footer (see CITATION.cff). */
export const APP_VERSION = "0.1.0";
/** Public contact address; NEXT_PUBLIC_CONTACT_EMAIL overrides it at build time. */
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "contact@krinea.org";
/** Public marketing routes (path without locale prefix). */
export const PUBLIC_ROUTES = ["", "/pricing", "/about", "/contact", "/security", "/privacy", "/terms", "/legal"] as const;
export const localePath = (locale: string, path: string) => (locale === "en" ? path || "/" : `/${locale}${path}`);
