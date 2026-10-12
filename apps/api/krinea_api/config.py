"""Settings, all from environment variables (a .env file is read if present)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(v: str | None, default: bool = False) -> bool:
    return default if v is None or not v.strip() else v.strip().lower() in ("1", "true", "yes", "on")


def _env(name: str, default: str = "") -> str:
    """An environment variable, with blank values treated as unset (dashboards such as Render's
    keep variables declared without a value as empty strings)."""
    value = os.environ.get(name, "").strip()
    return value or default


def _normalise_db_url(url: str) -> str:
    """Managed PostgreSQL providers (Render, Heroku, Supabase…) hand out postgres:// or
    postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver spelled out."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# Placeholder values shipped in examples and defaults: never acceptable in production.
WEAK_SECRETS = frozenset({"change-me", "change-me-in-production", "dev-secret-change-me"})
MIN_SECRET_LENGTH = 16


def check_secret_key(secret_key: str) -> None:
    """Refuse a production start with a missing, short or placeholder SECRET_KEY: it signs the
    Google sign-in state, encrypts users' provider keys and authenticates the web proxy."""
    key = (secret_key or "").strip()
    if not key:
        problem = "is empty"
    elif key.lower() in WEAK_SECRETS:
        problem = f"is the placeholder value {key!r}"
    elif len(key) < MIN_SECRET_LENGTH:
        problem = f"is shorter than {MIN_SECRET_LENGTH} characters"
    else:
        return
    raise RuntimeError(
        f"SECRET_KEY {problem}; refusing to start with KRINEA_ENV=production. Set SECRET_KEY to a long "
        "random value, e.g. the output of: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")


class Settings:
    def __init__(self) -> None:
        self.env = _env("KRINEA_ENV", "development")          # development | test | production
        self.debug = self.env != "production"
        self.secret_key = _env("SECRET_KEY", "dev-secret-change-me")
        self.database_url = _normalise_db_url(_env("DATABASE_URL", "sqlite:///./krinea.db"))
        self.data_dir = Path(_env("DATA_DIR", "./data")).resolve()
        # Public URLs. The browser reaches the API through the web app's /api proxy (D-23), so
        # BASE_URL is enough; both can be left unset when the web app runs the proxy (see urls.py).
        self.base_url = _env("BASE_URL", "http://localhost:3000").rstrip("/")   # the web app
        self.base_url_explicit = bool(_env("BASE_URL"))
        self.api_url = _env("API_URL", f"{self.base_url}/api").rstrip("/")    # as seen by browsers
        self.api_url_explicit = bool(_env("API_URL"))
        self.cors_origins = [o.strip() for o in _env("CORS_ORIGINS", self.base_url).split(",") if o.strip()]
        self.cookie_name = "krinea_session"
        self.cookie_secure = _bool(os.environ.get("COOKIE_SECURE"), self.env == "production")
        self.session_days = int(_env("SESSION_DAYS", "30"))
        self.magic_link_minutes = int(_env("MAGIC_LINK_MINUTES", "20"))
        self.email_provider = _env("EMAIL_PROVIDER", "console")          # console | resend | smtp
        self.resend_api_key = _env("RESEND_API_KEY", "")
        # SMTP (any mailbox: OVHcloud ssl0.ovh.net:465 for krinea.org, Gmail with an app password…)
        self.smtp_host = _env("SMTP_HOST", "")
        self.smtp_port = int(_env("SMTP_PORT", "587"))
        self.smtp_user = _env("SMTP_USER", "")
        # Sender: EMAIL_FROM; otherwise the SMTP mailbox itself (OVHcloud and Gmail only relay
        # mail sent from the authenticated address); otherwise no-reply@krinea.org.
        smtp_from = self.email_provider == "smtp" and "@" in self.smtp_user
        self.email_from = (_env("EMAIL_FROM")
                           or (f"Krinea <{self.smtp_user}>" if smtp_from else "Krinea <no-reply@krinea.org>"))
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")      # kept verbatim
        self.smtp_starttls = _bool(os.environ.get("SMTP_STARTTLS"), True)
        self.smtp_tls = _env("SMTP_TLS").lower()          # "" | ssl | starttls
        self.s3_bucket = _env("S3_BUCKET", "")
        self.s3_endpoint = _env("S3_ENDPOINT_URL", "")
        self.s3_region = _env("S3_REGION", "auto")
        self.inline_jobs = _bool(os.environ.get("INLINE_JOBS"), self.env != "production")
        self.unpaywall_email = _env("UNPAYWALL_EMAIL", "")
        self.server_ai_keys = {                                                      # D-16: included credits
            "claude": _env("ANTHROPIC_API_KEY", ""),
            "gemini": _env("GEMINI_API_KEY", ""),
            "deepseek": _env("DEEPSEEK_API_KEY", ""),
        }
        self.free_ai_tokens_per_month = int(_env("FREE_AI_TOKENS_PER_MONTH", "0"))
        self.pro_ai_tokens_per_month = int(_env("PRO_AI_TOKENS_PER_MONTH", "5000000"))
        self.max_upload_mb = int(_env("MAX_UPLOAD_MB", "200"))
        self.google_client_id = _env("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = _env("GOOGLE_CLIENT_SECRET", "")
        if self.env == "production":
            check_secret_key(self.secret_key)

    @property
    def is_test(self) -> bool:
        return self.env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
