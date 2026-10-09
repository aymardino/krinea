# Hosting on Render

Two editions share this repository.

## A · Tamis product (web + API + worker + PostgreSQL)

`render.yaml` at the repository root is a Render Blueprint. It declares a
PostgreSQL database (`tamis-db`), the API web service (`tamis-api`, Docker,
`apps/api/Dockerfile`), the background worker (`tamis-worker`, same image,
`python -m tamis_api.worker`) and the web front end (`tamis-web`, Docker,
`apps/web/Dockerfile`, Next.js standalone). Region: Frankfurt (EU).

Browsers only ever talk to `tamis-web`: it proxies `/api/*` to `tamis-api`
over Render's private network (decision D-23). So the deployment works on
the default `https://tamis-web-xxxx.onrender.com` address with no domain
and no URL to configure, and the session cookie is first-party.

1. In Render: **New → Blueprint**, select the repository. Review the four
   services and the database, then **Apply**.
2. Set the secrets marked `sync: false` on `tamis-api` and `tamis-worker`:
   `RESEND_API_KEY` (transactional e-mail; leave empty while testing, then
   magic links and invitations are only printed in the API logs), `S3_BUCKET`,
   `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (an
   S3-compatible bucket such as Cloudflare R2 or Backblaze B2 for PDFs),
   optionally `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` for
   included AI credits, `UNPAYWALL_EMAIL`, and `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET` for "Sign in with Google" (authorised redirect URI
   `https://<web host>/api/auth/google/callback`). `SECRET_KEY` is generated
   by Render and shared with the worker and the web proxy.
3. Open the `tamis-web` URL, create an account, done. Password accounts need
   no e-mail; magic links need `RESEND_API_KEY`.
4. Without a bucket, attach a persistent disk to `tamis-api` mounted at
   `/data` (paid instance, single instance) and leave `S3_BUCKET` empty; the
   worker then needs the same disk, which Render does not share, so prefer the
   bucket.
5. Deploys: every push to `main` redeploys; preview environments can be
   enabled per pull request. Rollback from the service's **Events** page.
6. Database: Render takes daily backups on paid PostgreSQL plans; export with
   `pg_dump` for off-site copies. Render's connection string (`postgres://…`)
   is accepted as is; the API rewrites it for the psycopg driver.

### Custom domain

1. Buy the domain at a registrar (Cloudflare Registrar, Porkbun, OVH, Gandi…).
2. In Render, `tamis-web` → **Settings → Custom domains → Add**: enter the
   apex (`example.org`) and Render also proposes `www`. It shows the DNS
   records to create at the registrar: an `A` record for the apex to Render's
   IP and a `CNAME` for `www` to the `onrender.com` host. On Cloudflare DNS,
   keep the records "DNS only" (grey cloud) until the certificate is issued.
3. Wait for **Verified** and the certificate (minutes to an hour). Nothing
   needs an `api.` subdomain: the API stays behind the web app's `/api`.
4. On `tamis-api`, set `BASE_URL` to `https://example.org` (links in e-mails
   then always use the domain, even for requests reaching the old
   `onrender.com` host) and `EMAIL_FROM` to an address on a domain verified
   in Resend. Update the Google OAuth redirect URI to
   `https://example.org/api/auth/google/callback`.

### If something fails

- **"Server failure" mails / `tamis-api` restarting**: open the service's
  **Logs**. A traceback at startup means a bad environment variable (most
  often `DATABASE_URL`); `/health` must answer `{"ok": true}`.
- **"The API is not reachable"** (a `502` from `/api/...`): `tamis-web`
  cannot reach the API. The response body names the `target` it tried and
  the error `code`; the same line is in `tamis-web`'s logs. Check, in this
  order: `tamis-api` shows **Deployed** (not "Failed deploy"); `API_URL` on
  `tamis-web` → **Environment** is the API's private address
  (`tamis-api-xxxx:10000`), not empty and not `localhost`. Blueprint
  references are filled in at sync time, so if the API failed to build during
  the first sync, click **Manual sync** on the Blueprint once it is green.
  Free instances cannot receive private traffic: with `plan: free`, set
  `API_URL` to the API's public `https://….onrender.com` URL instead.
- **"Something went wrong"** elsewhere: open the browser's network tab and
  read the failing `/api/...` response. A `401` right after signing in means
  the session cookie did not come back: `COOKIE_SECURE` must be `true` only
  behind HTTPS.
- **No e-mail arrives** (magic link, invitation): the API only logs e-mails
  until a provider is configured on `tamis-api`. Without a domain, use any
  mailbox over SMTP: `EMAIL_PROVIDER=smtp`, `SMTP_HOST=smtp.gmail.com`,
  `SMTP_PORT=587`, `SMTP_USER=you@gmail.com`, `SMTP_PASSWORD=<16-character
  Google app password>`, `EMAIL_FROM=Tamis <you@gmail.com>` (Google: Account →
  Security → 2-step verification → App passwords; about 500 messages a day).
  With a domain, prefer Resend: `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`,
  `EMAIL_FROM` on the domain verified in Resend. A failed delivery now returns
  a `502` with the reason instead of a silent success. Password sign-up needs
  no e-mail.
- **Blueprint sync errors on `fromService`**: replace the reference with a
  plain `value` (the API's public URL for `API_URL`, the API's `SECRET_KEY`
  for `PROXY_KEY`) and sync again.

Costs scale with instance sizes; three Starter services plus the entry
PostgreSQL plan are in the tens of dollars per month. For a test, the
comment at the top of `render.yaml` describes a cheaper layout (free
instances, no worker). Check render.com/pricing.

## B · Streamlit edition (single container)

The root `Dockerfile` builds the original Streamlit workbench
(`review_app.py`) with SQLite in `/data`. Deploy it as one Docker web service
with a persistent disk at `/data`, environment `DATA_DIR=/data`, `APP_LANG`
and optional provider keys. Health check `/_stcore/health`. Put it behind
Cloudflare Access or similar: Streamlit has no login.

## C · Anywhere else

`docker compose up --build` runs the full product on one machine
(PostgreSQL, API, worker, web) with `.env` from `.env.example`. The same
images run on Fly.io, Railway, a VPS or a university server.
