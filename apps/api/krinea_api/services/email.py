"""Transactional email: console (development, tests), Resend, or any SMTP mailbox."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from krinea_api.config import get_settings

log = logging.getLogger("krinea.email")
OUTBOX: list[dict] = []          # console provider keeps the last messages (tests read them)


class EmailError(Exception):
    """The message could not be handed to the provider (bad credentials, host down…)."""

_T = {
    "en": {
        "magic_subject": "Your sign-in link for Krinea",
        "magic_body": "Hello,\n\nClick to sign in to Krinea (valid for {minutes} minutes):\n{url}\n\nIf you did not request this, ignore this message.",
        "invite_subject": "{inviter} invited you to the review “{title}” on Krinea",
        "invite_body": "Hello,\n\n{inviter} invited you to join the review “{title}” as {role}.\nAccept the invitation:\n{url}\n\nThe link expires in 14 days.",
    },
    "fr": {
        "magic_subject": "Votre lien de connexion Krinea",
        "magic_body": "Bonjour,\n\nCliquez pour vous connecter à Krinea (valable {minutes} minutes) :\n{url}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
        "invite_subject": "{inviter} vous invite à la revue « {title} » sur Krinea",
        "invite_body": "Bonjour,\n\n{inviter} vous invite à rejoindre la revue « {title} » en tant que {role}.\nAccepter l'invitation :\n{url}\n\nLe lien expire dans 14 jours.",
    },
}


def _t(locale: str, key: str, **kw) -> str:
    return _T.get(locale, _T["en"])[key].format(**kw)


def configured() -> str:
    """Which provider will actually deliver: "resend", "smtp", "console" (logs only) or "" (misconfigured)."""
    s = get_settings()
    if s.email_provider == "resend":
        return "resend" if s.resend_api_key else ""
    if s.email_provider == "smtp":
        return "smtp" if s.smtp_host and s.smtp_user and s.smtp_password else ""
    return "console"


def available() -> bool:
    """Can this deployment send real e-mail? (The console provider only counts in development.)"""
    kind = configured()
    return kind in ("resend", "smtp") or (kind == "console" and get_settings().debug)


def send(to: str, subject: str, text: str) -> None:
    s = get_settings()
    kind = configured()
    if not kind:
        log.error("e-mail misconfigured: EMAIL_PROVIDER=%s but its settings are incomplete", s.email_provider)
        raise EmailError("E-mail is not configured on this server (EMAIL_PROVIDER=%s)" % s.email_provider)
    if kind == "console" and not s.debug:
        log.error("e-mail not configured in production (EMAIL_PROVIDER=console)")
        raise EmailError("E-mail is not configured on this server")
    if kind == "resend":
        try:
            r = httpx.post("https://api.resend.com/emails", timeout=15,
                           headers={"Authorization": f"Bearer {s.resend_api_key}"},
                           json={"from": s.email_from, "to": [to], "subject": subject, "text": text})
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.error("Resend refused the message: %s", e)
            raise EmailError("The e-mail provider refused the message") from e
        return
    if kind == "smtp":
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.email_from, to, subject
        msg.set_content(text)
        try:
            # Port 465 = implicit TLS (OVH, Gmail both accept it); 587 = STARTTLS.
            if s.smtp_port == 465 or s.smtp_tls == "ssl":
                smtp = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20)
            else:
                smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
            with smtp:
                if s.smtp_starttls and not isinstance(smtp, smtplib.SMTP_SSL):
                    smtp.starttls()
                smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
        except smtplib.SMTPAuthenticationError as e:
            log.error("SMTP login refused for %s at %s:%s: %s", s.smtp_user, s.smtp_host, s.smtp_port, e)
            raise EmailError("The mailbox refused the SMTP login (check SMTP_USER / SMTP_PASSWORD)") from e
        except (smtplib.SMTPException, OSError) as e:
            log.error("SMTP delivery failed via %s:%s: %s", s.smtp_host, s.smtp_port, e)
            raise EmailError(f"The e-mail could not be sent (SMTP {s.smtp_host}:{s.smtp_port}: {type(e).__name__})") from e
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
