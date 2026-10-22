# Krinea API

FastAPI + SQLAlchemy. PostgreSQL in production, SQLite by default locally.
Licence: AGPL-3.0-only.

```bash
pip install -e packages/core -e "apps/api[dev]"
cd apps/api
uvicorn krinea_api.main:app --reload          # http://localhost:8000/docs
python -m krinea_api.worker                   # only needed when INLINE_JOBS=0 (production)
python -m pytest -q
```

Authentication is a session cookie (`krinea_session`, HttpOnly) or `Authorization: Bearer`.
All review endpoints check membership and role (viewer < reviewer < admin < owner).

## Environment

Every setting is an environment variable, read once by `krinea_api/config.py`; a `.env`
file in the working directory is loaded if present. The defaults suit local development.

**On a public server, set `KRINEA_ENV=production`.** The Docker image does so already.
Production mode turns off debug behaviour (API docs at `/docs`, invitation and sign-in
links echoed in responses, e-mails only logged), makes cookies `Secure`, sends jobs to the
worker, and refuses to start when `SECRET_KEY` is empty, shorter than 16 characters or a
placeholder (`change-me`, `change-me-in-production`, `dev-secret-change-me`).

| Variable | Default | Meaning |
|---|---|---|
| `KRINEA_ENV` | `development` | `development`, `test` or `production`. Anything but `production` is debug mode. |
| `SECRET_KEY` | `dev-secret-change-me` | Encrypts users' AI provider keys, signs the Google sign-in state and authenticates the web proxy (equal to the web app's `PROXY_KEY`). Required in production: 16 characters or more, not a placeholder. |
| `DATABASE_URL` | `sqlite:///./krinea.db` | SQLAlchemy URL. `postgres://` and `postgresql://` URLs are rewritten for the psycopg 3 driver. |
| `DATA_DIR` | `./data` | Folder for PDFs when `S3_BUCKET` is empty (`/data` in the Docker image). |
| `BASE_URL` | `http://localhost:3000` | Public URL of the web app. Links in e-mails (sign-in, invitations) and Google redirects are built from it when it is set; otherwise from the origin reported by the web proxy. Required in production. |
| `API_URL` | `<BASE_URL>/api` | Address at which browsers reach the API. Leave unset when the web app proxies `/api` (the Google callback then uses the proxy's origin). |
| `CORS_ORIGINS` | `BASE_URL` | Comma-separated origins allowed to call the API directly. Only matters when the API is called without the proxy. |
| `COOKIE_SECURE` | `true` in production, else `false` | `Secure` flag of the session cookie; `true` only behind HTTPS. |
| `SESSION_DAYS` | `30` | Lifetime of a sign-in session. |
| `MAGIC_LINK_MINUTES` | `20` | Validity of a sign-in link sent by e-mail. |
| `EMAIL_PROVIDER` | `console` | `console` (log only, development), `smtp` or `resend`. In production only `smtp` or `resend` with complete settings can send; otherwise sending fails with `502` and the sign-in page hides the e-mail-link option. |
| `EMAIL_FROM` | see meaning | Sender. Default: `Krinea <SMTP_USER>` when `EMAIL_PROVIDER=smtp` and `SMTP_USER` is an address, otherwise `Krinea <no-reply@krinea.org>`. With Resend it must be on a verified domain. |
| `ADMIN_EMAILS` | empty | Comma-separated addresses allowed on the operator dashboard (`/app/admin`, API `GET /admin/overview`). |
| `AUDIENCE_STATS` | `1` | Cookie-free counts of the public pages' visits (`POST /stats/view`, reported by the web app). `0` stores nothing; set the same variable on the web app so that it sends nothing. |
| `NOTIFY_SIGNUPS_TO` | first administrator | Receives a short e-mail at each account creation (address, method, language). Empty with no administrator: no notice. |
| `RESEND_API_KEY` | empty | Resend API key (`EMAIL_PROVIDER=resend`). |
| `SMTP_HOST` | empty | SMTP server, e.g. `ssl0.ovh.net` (OVHcloud) or `smtp.gmail.com`. |
| `SMTP_PORT` | `587` | `465` means implicit TLS; other ports use STARTTLS. |
| `SMTP_USER` | empty | Mailbox login, usually the full address. |
| `SMTP_PASSWORD` | empty | Mailbox password (Gmail: an app password). |
| `SMTP_TLS` | empty | `ssl` forces implicit TLS on any port. |
| `SMTP_STARTTLS` | `true` | Set `false` to skip STARTTLS on a non-TLS port (local test servers only). |
| `S3_BUCKET` | empty | S3-compatible bucket for PDFs (keys under `pdfs/`). Empty: `DATA_DIR`. Required when a separate worker runs. |
| `S3_ENDPOINT_URL` | empty | Endpoint of an S3-compatible service (Cloudflare R2, Backblaze B2…); empty for AWS. |
| `S3_REGION` | `auto` | Region passed to the S3 client. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | empty | Bucket credentials, read by boto3 itself. |
| `INLINE_JOBS` | `false` in production, else `true` | `true`: jobs (deduplication, AI batches, extraction) run inside the API request; `false`: they are queued for `python -m krinea_api.worker`. |
| `UNPAYWALL_EMAIL` | empty | Contact address sent to Unpaywall for the open-access PDF lookup. |
| `ANTHROPIC_API_KEY` | empty | Server key for included AI credits (Claude). Empty: users bring their own key. |
| `GEMINI_API_KEY` | empty | Same, for Google Gemini. |
| `DEEPSEEK_API_KEY` | empty | Same, for DeepSeek. |
| `FREE_AI_TOKENS_PER_MONTH` | `0` | Included AI tokens per month on the Free plan. |
| `PRO_AI_TOKENS_PER_MONTH` | `5000000` | Included AI tokens per month on the Pro plan (Institution: four times this). |
| `MAX_UPLOAD_MB` | `200` | Largest accepted upload. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | empty | OAuth client for "Sign in with Google"; the button appears when both are set. |

The worker uses the same variables. Besides running jobs, it deletes sign-in-link tokens
older than a day and expired sessions, at most once an hour.

Deployment: `docs/deploy-render.md` at the repository root; `.env.example` and
`docker-compose.yml` show a full production setup.
