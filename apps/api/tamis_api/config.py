"""Settings, all from environment variables (a .env file is read if present)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(v: str | None, default: bool = False) -> bool:
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.env = os.environ.get("TAMIS_ENV", "development")          # development | test | production
        self.debug = self.env != "production"
        self.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
        self.database_url = os.environ.get("DATABASE_URL", "sqlite:///./tamis.db")
        self.data_dir = Path(os.environ.get("DATA_DIR", "./data")).resolve()
        self.base_url = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")   # the web app
        self.api_url = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
        self.cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", self.base_url).split(",") if o.strip()]
        self.cookie_name = "tamis_session"
        self.cookie_secure = _bool(os.environ.get("COOKIE_SECURE"), self.env == "production")
        self.session_days = int(os.environ.get("SESSION_DAYS", "30"))
        self.magic_link_minutes = int(os.environ.get("MAGIC_LINK_MINUTES", "20"))
        self.email_provider = os.environ.get("EMAIL_PROVIDER", "console")          # console | resend
        self.email_from = os.environ.get("EMAIL_FROM", "Tamis <no-reply@tamis.app>")
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "")
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

    @property
    def is_test(self) -> bool:
        return self.env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
