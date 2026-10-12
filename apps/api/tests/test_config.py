"""Settings: the production SECRET_KEY guard and the e-mail sender default."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import krinea_api
import krinea_core
from krinea_api.config import Settings


@pytest.mark.parametrize("secret", ["", "   ", "short-secret", "change-me", "change-me-in-production",
                                    "dev-secret-change-me", "CHANGE-ME-IN-PRODUCTION"])
def test_production_refuses_a_weak_secret_key(monkeypatch, secret):
    monkeypatch.setenv("KRINEA_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", secret)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings()


def test_secret_key_guard_accepts_a_real_key(monkeypatch):
    monkeypatch.setenv("KRINEA_ENV", "production")
    monkeypatch.delenv("SECRET_KEY")
    with pytest.raises(RuntimeError, match="placeholder"):          # unset -> the built-in default
        Settings()
    monkeypatch.setenv("SECRET_KEY", "k3Jx9-random-value-of-32-chars-ok")
    assert Settings().env == "production"
    monkeypatch.setenv("KRINEA_ENV", "development")                  # outside production: no check
    monkeypatch.setenv("SECRET_KEY", "change-me")
    assert Settings().secret_key == "change-me"


def test_api_and_worker_refuse_to_start(tmp_path):
    """The real entry points fail before serving anything."""
    paths = [str(Path(m.__file__).resolve().parents[1]) for m in (krinea_api, krinea_core)]
    env = {**os.environ, "KRINEA_ENV": "production", "SECRET_KEY": "change-me-in-production",
           "DATABASE_URL": f"sqlite:///{tmp_path}/x.db",
           "PYTHONPATH": os.pathsep.join(paths + [os.environ.get("PYTHONPATH", "")])}
    for code in ("import krinea_api.main", "from krinea_api.db import create_all; create_all()"):
        r = subprocess.run([sys.executable, "-c", code], env=env, cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode != 0 and "SECRET_KEY is the placeholder value" in r.stderr, r.stderr[-2000:]


def test_sender_address_defaults(monkeypatch):
    monkeypatch.setenv("EMAIL_FROM", "")                    # as left empty in .env.example
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_USER", "contact@krinea.org")
    monkeypatch.setenv("SMTP_PORT", "")
    s = Settings()
    assert s.email_from == "Krinea <contact@krinea.org>" and s.smtp_port == 587
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    assert Settings().email_from == "Krinea <no-reply@krinea.org>"
    monkeypatch.setenv("EMAIL_FROM", "Krinea <hello@krinea.org>")
    assert Settings().email_from == "Krinea <hello@krinea.org>"
