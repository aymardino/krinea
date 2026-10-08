# Hosting on Render

Two situations: the current Streamlit edition (one container), and the
product web application (several services). Both use the repository's
`render.yaml` as the source of truth once the product exists.

## A · Streamlit edition (today)

1. Push the repository to GitHub (done: `aymardino/systematic_review`).
2. In the Render dashboard: **New → Blueprint**, pick the repository. Render
   reads `render.yaml` and proposes one web service `systematic-review`
   (Docker) with a 5 GB disk mounted on `/data`.
3. Choose the instance type. Persistent disks require a paid instance
   (Starter or above); the free tier loses the database at every deploy.
4. Fill the environment variables marked `sync: false`:
   `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` (any subset),
   `UNPAYWALL_EMAIL`. `DATA_DIR=/data` and `APP_LANG` are preset.
5. Deploy. Health check: `/_stcore/health`. The container listens on the
   `PORT` Render injects.
6. Custom domain: **Settings → Custom domains → Add**, then create the CNAME
   (or ALIAS/ANAME for the apex) at the registrar. TLS is automatic.
7. Access control: Streamlit has no login. Put the service behind
   Cloudflare Access (Zero Trust, free for small teams) or keep the URL
   private until the product's accounts exist.
8. Backups: download `review.db` from the sidebar after each session, or add
   a Render cron job that copies `/data` to an S3-compatible bucket nightly.

Rollback: Render keeps previous deploys; **Manual deploy → Rollback**.
The disk is not versioned; restore from a backup copy.

## B · Product web application (next)

Services, all declared in `render.yaml`:

| Service | Type on Render | Notes |
| --- | --- | --- |
| `api` | Web service (Docker, FastAPI) | `api.<domain>`; autoscaling possible, no disk |
| `web` | Web service (Node, Next.js) | `<domain>`; marketing site + app |
| `worker` | Background worker | imports, dedup, AI batches, PDF text extraction |
| `db` | Render PostgreSQL | managed, daily backups, point-in-time recovery on paid plans |
| `cache` | Render Key Value (Redis-compatible) | job queue and sessions |
| PDFs | Cloudflare R2 or Backblaze B2 (S3 API) | Render has no object storage; buckets are cheap and durable |
| email | Resend or Postmark | sign-in links, invitations |
| cron | Render cron job | nightly exports/backups, Unpaywall refresh |

Steps: create the Blueprint from the repository; Render provisions database
and cache and injects their connection strings as environment variables;
add the bucket credentials, email API key and Stripe keys as secrets; map
the apex domain to `web` and `api.` to `api`; enable preview environments
for pull requests. Costs scale with instance sizes; the smallest paid
instances for `web`, `api`, `worker`, plus the entry PostgreSQL and Key
Value plans, are in the tens of dollars per month in total. Check
render.com/pricing for current figures before committing.

Alternatives with the same Docker images: Fly.io, Railway, a VPS with
Docker Compose (the `docker-compose.yml` in the repository), or a university
server.
