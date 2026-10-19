"""Operator notifications: a short e-mail to the maintainer when someone signs up."""
from __future__ import annotations

import logging

from krinea_api.config import get_settings
from krinea_api.services import email as email_service

log = logging.getLogger("krinea.notify")


def signup_notice(email: str, name: str, method: str, locale: str = "") -> None:
    """Sent as a FastAPI background task after the sign-up response; never raises, so a mail
    problem can never block an account creation. Needs NOTIFY_SIGNUPS_TO (or ADMIN_EMAILS)."""
    s = get_settings()
    to = s.notify_signups_to
    if not to:
        return
    try:
        who = f"{name} <{email}>" if name else email
        text = ("A new account was created on Krinea.\n\n"
                f"Who: {who}\nSign-up method: {method}\nInterface language: {locale or 'en'}\n\n"
                f"Administration: {s.base_url}/app/admin\n")
        email_service.send(to, f"[Krinea] New account: {email}", text)
    except Exception:  # noqa: BLE001 (any provider failure is logged, not raised)
        log.exception("sign-up notice to %s failed", to)
