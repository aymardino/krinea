"""Transactional email: console (development, tests) or Resend (production)."""
from __future__ import annotations

import logging

import httpx

from tamis_api.config import get_settings

log = logging.getLogger("tamis.email")
OUTBOX: list[dict] = []          # console provider keeps the last messages (tests read them)

_T = {
    "en": {
        "magic_subject": "Your sign-in link for Tamis",
        "magic_body": "Hello,\n\nClick to sign in to Tamis (valid for {minutes} minutes):\n{url}\n\nIf you did not request this, ignore this message.",
        "invite_subject": "{inviter} invited you to the review “{title}” on Tamis",
        "invite_body": "Hello,\n\n{inviter} invited you to join the review “{title}” as {role}.\nAccept the invitation:\n{url}\n\nThe link expires in 14 days.",
    },
    "fr": {
        "magic_subject": "Votre lien de connexion Tamis",
        "magic_body": "Bonjour,\n\nCliquez pour vous connecter à Tamis (valable {minutes} minutes) :\n{url}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
        "invite_subject": "{inviter} vous invite à la revue « {title} » sur Tamis",
        "invite_body": "Bonjour,\n\n{inviter} vous invite à rejoindre la revue « {title} » en tant que {role}.\nAccepter l'invitation :\n{url}\n\nLe lien expire dans 14 jours.",
    },
}


def _t(locale: str, key: str, **kw) -> str:
    return _T.get(locale, _T["en"])[key].format(**kw)


def send(to: str, subject: str, text: str) -> None:
    s = get_settings()
    if s.email_provider == "resend" and s.resend_api_key:
        r = httpx.post("https://api.resend.com/emails", timeout=15,
                       headers={"Authorization": f"Bearer {s.resend_api_key}"},
                       json={"from": s.email_from, "to": [to], "subject": subject, "text": text})
        r.raise_for_status()
        return
    OUTBOX.append({"to": to, "subject": subject, "text": text})
    del OUTBOX[:-50]
    log.info("EMAIL to=%s subject=%s\n%s", to, subject, text)


def send_magic_link(to: str, url: str, locale: str = "en") -> None:
    s = get_settings()
    send(to, _t(locale, "magic_subject"), _t(locale, "magic_body", url=url, minutes=s.magic_link_minutes))


def send_invitation(to: str, inviter: str, title: str, role: str, url: str, locale: str = "en") -> None:
    send(to, _t(locale, "invite_subject", inviter=inviter, title=title),
         _t(locale, "invite_body", inviter=inviter, title=title, role=role, url=url))
