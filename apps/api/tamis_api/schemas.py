"""Pydantic request/response models."""
from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class Ok(BaseModel):
    ok: bool = True


# ── Auth ─────────────────────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(default="", max_length=200)
    locale: str = "en"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class MagicLinkIn(BaseModel):
    email: EmailStr
    locale: str = "en"


class TokenIn(BaseModel):
    token: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    locale: str
    plan: str
    created_at: dt.datetime
    email_verified: bool = False

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    locale: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class ProviderKeyIn(BaseModel):
    key: str = Field(min_length=8, max_length=500)


class ProviderKeyOut(BaseModel):
    provider: str
    masked: str
    created_at: dt.datetime


# ── Reviews ──────────────────────────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    question: str = ""
    review_type: str = "systematic"


class ReviewUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    question: str | None = None
    review_type: str | None = None
    criteria: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    extraction_schema: list[dict[str, Any]] | None = None
    is_archived: bool | None = None


class MemberOut(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    created_at: dt.datetime


class ReviewOut(BaseModel):
    id: str
    title: str
    description: str
    question: str
    review_type: str
    criteria: dict[str, Any]
    settings: dict[str, Any]
    extraction_schema: list[dict[str, Any]]
    is_archived: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    my_role: str = "viewer"
    members: list[MemberOut] = []
    counts: dict[str, Any] = {}

    class Config:
        from_attributes = True


class ReviewSummary(BaseModel):
    id: str
    title: str
    review_type: str
    my_role: str
    is_archived: bool
    updated_at: dt.datetime
    n_records: int = 0
    n_members: int = 1
    progress: float = 0.0


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "reviewer"

    @field_validator("role")
    @classmethod
    def _role(cls, v):
        if v not in ("admin", "reviewer", "viewer"):
            raise ValueError("role must be admin, reviewer or viewer")
        return v


class InvitationOut(BaseModel):
    id: str
    email: str
    role: str
    created_at: dt.datetime
    expires_at: dt.datetime
    accepted_at: dt.datetime | None
    accept_url: str | None = None


class RoleIn(BaseModel):
    role: str


# ── Records ──────────────────────────────────────────────────────────────────────
class RecordOut(BaseModel):
    id: int
    title: str
    abstract: str
    authors: str
    year: str
    journal: str
    volume: str
    issue: str
    pages: str
    doi: str
    url: str
    keywords: str
    pmid: str
    type: str
    language: str
    source_db: str
    import_id: str | None
    is_duplicate: bool
    duplicate_of: int | None
    dup_score: float | None
    dup_reason: str
    pdf_status: str
    has_pdf: bool = False
    labels: str
    notes: str
    ta_status: str = "pending"
    ft_status: str = "pending"
    my_decision: dict[str, Any] | None = None
    decisions: list[dict[str, Any]] = []
    ai: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class RecordPage(BaseModel):
    items: list[RecordOut]
    total: int
    next_cursor: int | None = None


class RecordUpdate(BaseModel):
    labels: str | None = None
    notes: str | None = None
    title: str | None = None
    abstract: str | None = None
    year: str | None = None
    doi: str | None = None


class DecisionIn(BaseModel):
    stage: str = "ta"
    decision: str
    reason: str = ""
    note: str = ""
    seconds: float | None = None
    as_consensus: bool = False

    @field_validator("stage")
    @classmethod
    def _stage(cls, v):
        if v not in ("ta", "ft"):
            raise ValueError("stage must be ta or ft")
        return v

    @field_validator("decision")
    @classmethod
    def _decision(cls, v):
        if v not in ("include", "maybe", "exclude"):
            raise ValueError("decision must be include, maybe or exclude")
        return v


class BulkDecisionIn(BaseModel):
    record_ids: list[int]
    stage: str = "ta"
    decision: str
    reason: str = ""


class DedupRunIn(BaseModel):
    auto_threshold: float = 95.0
    review_threshold: float = 85.0


class CandidateOut(BaseModel):
    id: int
    score: float
    reason: str
    status: str
    a: RecordOut
    b: RecordOut


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: float
    result: dict[str, Any]
    error: str
    created_at: dt.datetime
    finished_at: dt.datetime | None

    class Config:
        from_attributes = True


class AIScreenIn(BaseModel):
    stage: str = "ta"
    record_ids: list[int] | None = None       # None = every pending record without a suggestion
    limit: int = 100
    provider: str | None = None
    model: str | None = None


class ExtractionRunIn(BaseModel):
    record_ids: list[int] | None = None
    provider: str | None = None
    model: str | None = None


class ExtractionVerifyIn(BaseModel):
    values: dict[str, Any]
    quotes: dict[str, Any] = {}
    seconds: float | None = None


class ExtractionOut(BaseModel):
    record_id: int
    status: str
    model: str
    values: dict[str, Any]
    quotes: dict[str, Any]
    ai_values: dict[str, Any]
    text_extracted: str = ""
    error: str
    created_at: dt.datetime
    verified_at: dt.datetime | None
    flags: dict[str, Any] = {}

    class Config:
        from_attributes = True
