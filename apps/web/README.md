# Krinea web

The Next.js front end of [Krinea](../../README.md): the public site (home, pricing, about,
security and legal pages) and the review workspace. The browser only talks to this app;
`/api/*` is proxied to the Krinea API, so cookies stay first-party and no CORS setup is needed.

## Develop

```bash
pnpm install
pnpm dev      # http://localhost:3000, expects the API on http://localhost:8000
pnpm build    # production build (standalone output, used by the Dockerfile)
```

Start the API first (see the [root README](../../README.md)).

## Configuration

Run time (read by the server, no rebuild needed):

| Variable | Purpose |
| --- | --- |
| `API_URL` | Internal address of the API that `/api/*` is proxied to. A full URL or a bare `host:port` (Render's `hostport`). Default `http://localhost:8000`. |
| `PROXY_KEY` | Shared secret sent with every proxied request; must equal the API's `SECRET_KEY`. |
| `PUBLIC_ORIGIN` | Public origin of the site (for example `https://krinea.org`), reported to the API for links in e-mails and OAuth redirects. In production the proxy never derives it from request headers; it uses `PUBLIC_ORIGIN`, else `NEXT_PUBLIC_SITE_URL`. Set it when the site is served elsewhere (a test deployment, a self-hosted domain). The API's `BASE_URL`, when set, takes precedence. |

Build time (inlined into the bundle, so a change needs a rebuild):

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_SITE_URL` | Canonical public address, used for metadata, the sitemap and social cards. Default `https://krinea.org`. |
| `NEXT_PUBLIC_CONTACT_EMAIL` | Address shown on the contact page. Default `contact@krinea.org`. |
| `NEXT_PUBLIC_API_URL` | Only for a separately hosted API that the browser calls directly. Leave empty to use the `/api` proxy. |

## Deploy

See [docs/deploy-render.md](../../docs/deploy-render.md) for the Render blueprint and the
[root README](../../README.md) for Docker Compose and self-hosting.
