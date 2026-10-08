"""AI assistance: key resolution (D-16), token metering, screening suggestions and
extraction drafts. The AI never writes a decision (D-10)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tamis_api import models
from tamis_api.config import get_settings
from tamis_api.security import decrypt_secret
from tamis_api.services import storage
from tamis_core import extraction_schema, llm
from tamis_core import screening as core_screening


class AIUnavailable(Exception):
    """No usable key: the caller turns it into a 402/400 for the client."""


def month_start() -> dt.datetime:
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def monthly_server_tokens(db: Session, user_id: str) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(models.AIUsage.input_tokens + models.AIUsage.output_tokens), 0))
                         .where(models.AIUsage.user_id == user_id, models.AIUsage.key_source == "server",
                                models.AIUsage.created_at >= month_start())) or 0)


def included_budget(user: models.User) -> int:
    s = get_settings()
    return {"free": s.free_ai_tokens_per_month, "pro": s.pro_ai_tokens_per_month,
            "institution": s.pro_ai_tokens_per_month * 4}.get(user.plan, 0)


def resolve_key(db: Session, user: models.User, provider: str) -> tuple[str, str]:
    """(api_key, 'user' | 'server'). The user's own key always wins."""
    pk = db.scalar(select(models.ProviderKey).where(models.ProviderKey.user_id == user.id,
                                                    models.ProviderKey.provider == provider))
    if pk:
        key = decrypt_secret(pk.encrypted_key)
        if key:
            return key, "user"
    server_key = get_settings().server_ai_keys.get(provider, "")
    budget = included_budget(user)
    if server_key and budget > 0:
        if monthly_server_tokens(db, user.id) < budget:
            return server_key, "server"
        raise AIUnavailable("Included AI credits for this month are used up. Add your own API key to continue.")
    raise AIUnavailable(f"No {provider} API key: add yours in Settings → AI providers.")


def usage_summary(db: Session, user: models.User) -> dict:
    used = monthly_server_tokens(db, user.id)
    own = int(db.scalar(select(func.coalesce(func.sum(models.AIUsage.input_tokens + models.AIUsage.output_tokens), 0))
                        .where(models.AIUsage.user_id == user.id, models.AIUsage.key_source == "user",
                               models.AIUsage.created_at >= month_start())) or 0)
    return {"month": month_start().strftime("%Y-%m"), "included_budget": included_budget(user),
            "included_used": used, "own_key_tokens": own}


def record_usage(db: Session, user: models.User | None, review_id: str | None, provider: str, model: str,
                 purpose: str, usage: llm.Usage, key_source: str) -> None:
    db.add(models.AIUsage(user_id=user.id if user else None, review_id=review_id, provider=provider,
                          model=model, purpose=purpose, key_source=key_source,
                          input_tokens=usage.input_tokens, output_tokens=usage.output_tokens))


def provider_and_model(review: models.Review, purpose: str, provider: str | None, model: str | None) -> tuple[str, str]:
    s = review.settings or {}
    provider = provider or s.get("ai_provider") or "claude"
    model = model or s.get(f"ai_model_{purpose}") or llm.DEFAULT_MODELS[purpose][provider]
    return provider, model


def record_dict(r: models.Record) -> dict:
    return {k: getattr(r, k) for k in ("title", "abstract", "authors", "year", "journal", "keywords", "doi")}


def screen_record(db: Session, review: models.Review, user: models.User, record: models.Record,
                  stage: str = "ta", provider: str | None = None, model: str | None = None) -> models.AISuggestion:
    provider, model = provider_and_model(review, "screening", provider, model)
    key, source = resolve_key(db, user, provider)
    full_text = ""
    if stage == "ft" and record.pdf_key:
        data = storage.read_pdf(record.pdf_key)
        if data:
            full_text = storage.pdf_text(data, max_chars=120_000)
    prompt = core_screening.build_screening_prompt(review.criteria or {}, record_dict(record), stage=stage,
                                                   full_text=full_text)
    raw, usage = llm.call_json(prompt, provider, key, model, purpose="screening", max_tokens=1024)
    s = core_screening.parse_suggestion(raw)
    record_usage(db, user, review.id, provider, model, "screening", usage, source)
    sug = db.scalar(select(models.AISuggestion).where(models.AISuggestion.record_id == record.id,
                                                      models.AISuggestion.stage == stage))
    if not sug:
        sug = models.AISuggestion(review_id=review.id, record_id=record.id, stage=stage)
        db.add(sug)
    sug.decision, sug.reason, sug.rationale = s["decision"], s["reason"][:200], s["rationale"]
    sug.confidence, sug.model, sug.created_at = float(s["confidence"]), model, models.now()
    db.commit()
    return sug


def extract_record(db: Session, review: models.Review, user: models.User, record: models.Record,
                   provider: str | None = None, model: str | None = None) -> models.Extraction:
    provider, model = provider_and_model(review, "extraction", provider, model)
    fields = extraction_schema.from_json(review.extraction_schema or [])
    ex = db.scalar(select(models.Extraction).where(models.Extraction.record_id == record.id))
    if not ex:
        ex = models.Extraction(review_id=review.id, record_id=record.id)
        db.add(ex)
    ex.model, ex.status, ex.error, ex.created_at = model, "draft", "", models.now()
    try:
        key, source = resolve_key(db, user, provider)
        data = storage.read_pdf(record.pdf_key) if record.pdf_key else None
        if not data:
            raise ValueError("No PDF on file for this record")
        text = storage.pdf_text(data)
        if len(text) < 500:
            raise ValueError("Extracted text too short — the PDF may be scanned (needs OCR)")
        prompt = extraction_schema.build_prompt(fields, text, context=review.question or "")
        raw, usage = llm.call_json(prompt, provider, key, model, purpose="extraction", max_tokens=8192)
        record_usage(db, user, review.id, provider, model, "extraction", usage, source)
        values, quotes = extraction_schema.clean_result(fields, raw)
        ex.values, ex.quotes, ex.ai_values, ex.text_extracted = values, quotes, dict(values), text
    except Exception as e:              # noqa: BLE001 — the failure is recorded on the draft
        ex.status, ex.error = "failed", f"{type(e).__name__}: {e}"
    db.commit()
    return ex
