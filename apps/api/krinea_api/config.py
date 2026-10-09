"""Settings, all from environment variables (a .env file is read if present)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(v: str | None, default: bool = False) -> bool:
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _normalise_db_url(url: str) -> str:
    """Managed PostgreSQL providers (Render, Heroku, Supabase…) hand out postgres:// or
    postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver spelled out."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings:
    def __init__(self) -> None:
        self.env = os.environ.get("KRINEA_ENV", "development")          # development | test | production
        self.debug = self.env != "production"
        self.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
        self.database_url = _normalise_db_url(os.environ.get("DATABASE_URL", "sqlite:///./krinea.db"))
        self.data_dir = Path(os.environ.get("DATA_DIR", "./data")).resolve()
        # Public URLs. The browser reaches the API through the web app's /api proxy (D-23), so
        # BASE_URL is enough; both can be left unset when the web app runs the proxy (see urls.py).
        self.base_url = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")   # the web app
        self.base_url_explicit = bool(os.environ.get("BASE_URL"))
        self.api_url = os.environ.get("API_URL", f"{self.base_url}/api").rstrip("/")    # as seen by browsers
        self.api_url_explicit = bool(os.environ.get("API_URL"))
        self.cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", self.base_url).split(",") if o.strip()]
        self.cookie_name = "krinea_session"
        self.cookie_secure = _bool(os.environ.get("COOKIE_SECURE"), self.env == "production")
        self.session_days = int(os.environ.get("SESSION_DAYS", "30"))
        self.magic_link_minutes = int(os.environ.get("MAGIC_LINK_MINUTES", "20"))
        self.email_provider = os.environ.get("EMAIL_PROVIDER", "console")          # console | resend | smtp
        self.email_from = os.environ.get("EMAIL_FROM", "Krinea <no-reply@krinea.app>")
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "")
        # SMTP (any mailbox, e.g. Gmail with an app password): no domain needed to get started
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.smtp_starttls = _bool(os.environ.get("SMTP_STARTTLS"), True)
        self.s3_bucket = os.environ.get("S3_BUCKET", "")
        self.s3_endpoint = os.environ.get("S3_ENDPOINT_URL", "")
        self.s3_region = os.environ.get("S3_REGION", "auto")
        self.inline_jobs = _bool(os.environ.get("INLINE_JOBS"), self.env != "production")
        self.unpaywall_email = os.environ.get("UNPAYWALL_EMAIL", "")
        self.server_ai_keys = {                                                      # D-16: included credits
            "claude": os.environ.get("ANTHROPIC_API_KEY", ""),
            "gemini": os.environ.get("GEMINI_API_KEY", ""),
            "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
        }
        self.free_ai_tokens_per_month = int(os.environ.get("FREE_AI_TOKENS_PER_MONTH", "0"))
        self.pro_ai_tokens_per_month = int(os.environ.get("PRO_AI_TOKENS_PER_MONTH", "5000000"))
        self.max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "200"))
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    @property
    def is_test(self) -> bool:
        return self.env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
