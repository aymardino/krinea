"""Accounts: register, password login, magic links, profile, provider keys."""
from __future__ import annotations

import logging

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession

from krinea_api import models, schemas
from krinea_api.config import get_settings
from krinea_api.urls import public_base_url
from krinea_api.db import get_db
from krinea_api.deps import current_user, optional_user
from krinea_api.security import (decrypt_secret, encrypt_secret, expires_in, hash_password, mask_key,
                                new_token, token_hash, verify_password)
from krinea_api.services import ai as ai_service
from krinea_api.services import email as email_service
from krinea_api.services import oauth

log = logging.getLogger("krinea.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def start_session(db: DBSession, user: models.User, request: Request, response: Response) -> str:
    s = get_settings()
    token = new_token()
    db.add(models.Session(user_id=user.id, token_hash=token_hash(token),
                          user_agent=request.headers.get("user-agent", "")[:300],
                          expires_at=expires_in(days=s.session_days)))
    user.last_login_at = models.now()
    db.commit()
    response.set_cookie(s.cookie_name, token, max_age=s.session_days * 86400, httponly=True,
                        samesite="lax", secure=s.cookie_secure, path="/")
    return token


def user_out(user: models.User) -> schemas.UserOut:
    return schemas.UserOut(id=user.id, email=user.email, name=user.name, locale=user.locale, plan=user.plan,
                           created_at=user.created_at, email_verified=user.email_verified_at is not None)


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(body: schemas.RegisterIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    email = body.email.lower().strip()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(409, "An account already exists for this email")
    user = models.User(email=email, name=body.name.strip(), password_hash=hash_password(body.password),
                       locale=body.locale if body.locale in ("en", "fr") else "en")
    db.add(user)
    db.flush()
    start_session(db, user, request, response)
    return user_out(user)


@router.post("/login", response_model=schemas.UserOut)
def login(body: schemas.LoginIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == body.email.lower().strip()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    if not user.is_active:
        raise HTTPException(403, "This account is disabled")
    start_session(db, user, request, response)
    return user_out(user)


@router.post("/logout", response_model=schemas.Ok)
def logout(request: Request, response: Response, db: DBSession = Depends(get_db),
           user: models.User | None = Depends(optional_user)):
    sid = getattr(request.state, "session_id", None)
    if sid:
        db.execute(delete(models.Session).where(models.Session.id == sid))
        db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")
    return schemas.Ok()


@router.post("/magic-link")
def magic_link(body: schemas.MagicLinkIn, request: Request, db: DBSession = Depends(get_db)):
    s = get_settings()
    email = body.email.lower().strip()
    token = new_token()
    db.add(models.LoginToken(email=email, token_hash=token_hash(token), purpose="login",
                             expires_at=expires_in(minutes=s.magic_link_minutes)))
    db.commit()
    url = f"{public_base_url(request)}/auth/magic?token={token}"
    email_service.send_magic_link(email, url, body.locale if body.locale in ("en", "fr") else "en")
    log.info("magic link sent to %s via %s", email, s.email_provider)
    out = {"ok": True}
    if s.debug:
        out["dev_link"] = url       # development only: no mail server needed
    return out


@router.post("/magic-link/verify", response_model=schemas.UserOut)
def magic_verify(body: schemas.TokenIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    lt = db.scalar(select(models.LoginToken).where(models.LoginToken.token_hash == token_hash(body.token)))
    now = models.now()
    if not lt or lt.used_at or lt.expires_at < now:
        reason = "unknown token" if not lt else ("already used" if lt.used_at else "expired")
        log.info("magic link refused (%s) for %s", reason, lt.email if lt else "?")
        raise HTTPException(400, "This link is invalid or has expired")
    lt.used_at = now
    user = db.scalar(select(models.User).where(models.User.email == lt.email))
    if not user:
        user = models.User(email=lt.email, name="", password_hash=None)
        db.add(user)
        db.flush()
    if not user.email_verified_at:
        user.email_verified_at = now
    start_session(db, user, request, response)
    return user_out(user)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)):
    return user_out(user)


@router.patch("/me", response_model=schemas.UserOut)
def update_me(body: schemas.UserUpdate, user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    if body.name is not None:
        user.name = body.name.strip()
    if body.locale in ("en", "fr"):
        user.locale = body.locale
    if body.password:
        user.password_hash = hash_password(body.password)
    db.commit()
    return user_out(user)


@router.get("/keys", response_model=list[schemas.ProviderKeyOut])
def list_keys(user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    rows = db.scalars(select(models.ProviderKey).where(models.ProviderKey.user_id == user.id)).all()
    return [schemas.ProviderKeyOut(provider=k.provider, masked=mask_key(decrypt_secret(k.encrypted_key)),
                                   created_at=k.created_at) for k in rows]


@router.put("/keys/{provider}", response_model=schemas.ProviderKeyOut)
def put_key(provider: str, body: schemas.ProviderKeyIn, user: models.User = Depends(current_user),
            db: DBSession = Depends(get_db)):
    if provider not in ("claude", "gemini", "deepseek"):
        raise HTTPException(400, "Unknown provider")
    k = db.scalar(select(models.ProviderKey).where(models.ProviderKey.user_id == user.id,
                                                   models.ProviderKey.provider == provider))
    if not k:
        k = models.ProviderKey(user_id=user.id, provider=provider, encrypted_key="")
        db.add(k)
    k.encrypted_key, k.created_at = encrypt_secret(body.key.strip()), models.now()
    db.commit()
    return schemas.ProviderKeyOut(provider=provider, masked=mask_key(body.key.strip()), created_at=k.created_at)


@router.delete("/keys/{provider}", response_model=schemas.Ok)
def delete_key(provider: str, user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    db.execute(delete(models.ProviderKey).where(models.ProviderKey.user_id == user.id,
                                                models.ProviderKey.provider == provider))
    db.commit()
    return schemas.Ok()


@router.get("/usage")
def usage(user: models.User = Depends(current_user), db: DBSession = Depends(get_db)):
    return ai_service.usage_summary(db, user)


# ── Sign in with Google ──────────────────────────────────────────────────────────
@router.get("/providers")
def providers():
    """Which sign-in methods are configured (the web app shows the buttons)."""
    return {"google": oauth.enabled(), "email": email_service.available()}


@router.get("/google/start")
def google_start(request: Request, next: str = "/app", locale: str = "en"):
    if not oauth.enabled():
        raise HTTPException(404, "Google sign-in is not configured")
    state, nonce = new_token(16), new_token(16)
    payload = {"state": state, "nonce": nonce, "next": oauth.safe_next(next),
               "locale": locale if locale in ("en", "fr") else "en"}
    resp = RedirectResponse(oauth.authorization_url(state, nonce, request), status_code=302)
    # path "/" because browsers see the callback under the web app's /api prefix (D-23)
    resp.set_cookie(oauth.STATE_COOKIE, oauth.sign_state(payload), max_age=oauth.STATE_MAX_AGE, httponly=True,
                    samesite="lax", secure=get_settings().cookie_secure, path="/")
    return resp


@router.get("/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", error: str = "",
                    db: DBSession = Depends(get_db)):
    s = get_settings()
    try:
        saved = oauth.load_state(request.cookies.get(oauth.STATE_COOKIE, ""))
    except oauth.OAuthError:
        saved = {}
    locale = saved.get("locale", "en")
    prefix = "" if locale == "en" else f"/{locale}"
    base = public_base_url(request)
    failure = RedirectResponse(f"{base}{prefix}/sign-in?error=google", status_code=302)
    failure.delete_cookie(oauth.STATE_COOKIE, path="/")
    if error or not code or not saved or saved.get("state") != state:
        return failure
    try:
        tokens = oauth.exchange_code(code, request)
        claims = oauth.verify_id_token(tokens.get("id_token", ""), saved.get("nonce"))
    except oauth.OAuthError:
        return failure
    email = str(claims["email"]).lower().strip()
    account = db.scalar(select(models.OAuthAccount).where(models.OAuthAccount.provider == "google",
                                                          models.OAuthAccount.subject == str(claims["sub"])))
    if account:
        user = db.get(models.User, account.user_id)
    else:
        user = db.scalar(select(models.User).where(models.User.email == email))
        if not user:
            user = models.User(email=email, name=str(claims.get("name") or "").strip()[:200], password_hash=None,
                               locale=locale)
            db.add(user)
            db.flush()
        db.add(models.OAuthAccount(user_id=user.id, provider="google", subject=str(claims["sub"]), email=email))
    if not user or not user.is_active:
        return failure
    if not user.email_verified_at:
        user.email_verified_at = models.now()
    if not user.name and claims.get("name"):
        user.name = str(claims["name"]).strip()[:200]
    resp = RedirectResponse(f"{base}{prefix}{saved.get('next', '/app')}", status_code=302)
    resp.delete_cookie(oauth.STATE_COOKIE, path="/")
    start_session(db, user, request, resp)
    return resp
