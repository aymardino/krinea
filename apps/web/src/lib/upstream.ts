/** Where the web app's /api proxy forwards requests (decision D-23).
 *  API_URL may be a full URL or a bare host[:port] such as Render's `hostport` property. */
/** API_URL may be a full URL or a bare host[:port] (Render's `hostport` property). */
export function upstreamUrl(raw: string | undefined): string {
  const value = (raw ?? "").trim().replace(/\/+$/, "") || "http://localhost:8000";
  if (/^https?:\/\//i.test(value)) return value;
  const [host, port] = value.split(":");
  const tls = port === "443" || (!port && /\.(onrender\.com|fly\.dev|railway\.app)$/i.test(host));
  return `${tls ? "https" : "http"}://${value}`;
}
