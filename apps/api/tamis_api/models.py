"""Database model. Ids: UUID strings for people and reviews, integers for the
bulk tables (records, decisions). Every table is scoped to a review."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tamis_api.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str | None] = mapped_column(String(300), nullable=True)
    locale: Mapped[str] = mapped_column(String(8), default="en")
    plan: Mapped[str] = mapped_column(String(20), default="free")        # free | pro | institution
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)


class LoginToken(Base):
    """Magic-link and invitation-style one-time tokens."""
    __tablename__ = "login_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(20), default="login")      # login | verify
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class ProviderKey(Base):
    """A user's own LLM provider key, encrypted at rest (D-16)."""
    __tablename__ = "provider_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    encrypted_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("user_id", "provider"),)


class OAuthAccount(Base):
    """An external identity (Google today, ORCID next) linked to a user."""
    __tablename__ = "oauth_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("provider", "subject"),)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    question: Mapped[str] = mapped_column(Text, default="")
    review_type: Mapped[str] = mapped_column(String(40), default="systematic")
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)          # inclusion, exclusion, reasons, keywords
    settings: Mapped[dict] = mapped_column(JSON, default=dict)          # required_reviewers, blind, ai model...
    extraction_schema: Mapped[list] = mapped_column(JSON, default=list)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="review", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="reviewer")    # owner | admin | reviewer | viewer
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("review_id", "user_id"),)

    review: Mapped[Review] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20), default="reviewer")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Import(Base):
    __tablename__ = "imports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    format: Mapped[str] = mapped_column(String(20), default="")
    source_db: Mapped[str] = mapped_column(String(120), default="")
    n_records: Mapped[int] = mapped_column(Integer, default=0)
    n_skipped: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    import_id: Mapped[str | None] = mapped_column(ForeignKey("imports.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    authors: Mapped[str] = mapped_column(Text, default="")
    year: Mapped[str] = mapped_column(String(8), default="")
    journal: Mapped[str] = mapped_column(Text, default="")
    volume: Mapped[str] = mapped_column(String(40), default="")
    issue: Mapped[str] = mapped_column(String(40), default="")
    pages: Mapped[str] = mapped_column(String(60), default="")
    doi: Mapped[str] = mapped_column(String(300), default="", index=True)
    url: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[str] = mapped_column(Text, default="")
    pmid: Mapped[str] = mapped_column(String(20), default="")
    publisher: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(60), default="")
    language: Mapped[str] = mapped_column(String(40), default="")
    source_db: Mapped[str] = mapped_column(String(200), default="")
    raw_id: Mapped[str] = mapped_column(String(200), default="")
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    duplicate_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dup_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dup_reason: Mapped[str] = mapped_column(String(200), default="")
    pdf_key: Mapped[str] = mapped_column(String(400), default="")
    pdf_status: Mapped[str] = mapped_column(String(20), default="")      # '' | available | not_retrieved
    labels: Mapped[str] = mapped_column(Text, default="")                 # ; separated, shared by the team
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_records_review_dup", "review_id", "is_duplicate"),)


class DedupCandidate(Base):
    __tablename__ = "dedup_candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    record_a: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    record_b: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")    # pending | merged | ignored
    __table_args__ = (UniqueConstraint("record_a", "record_b"),)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(10))                        # ta | ft
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer: Mapped[str] = mapped_column(String(64))                     # user id, or 'consensus'
    decision: Mapped[str] = mapped_column(String(10))                     # include | maybe | exclude
    reason: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    seconds: Mapped[float | None] = mapped_column(Float, nullable=True)    # time spent, for the dashboard
    decided_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("record_id", "stage", "reviewer"),)


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(10))
    decision: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(String(200), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    model: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("record_id", "stage"),)


class Extraction(Base):
    __tablename__ = "extractions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="draft")     # draft | verified | failed
    model: Mapped[str] = mapped_column(String(80), default="")
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    quotes: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_values: Mapped[dict] = mapped_column(JSON, default=dict)
    text_extracted: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Job(Base):
    """Database-backed job queue (D-17): dedup, AI batches, extraction batches."""
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str | None] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)   # queued | running | done | failed
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[float] = mapped_column(Float, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class AIUsage(Base):
    """Per-call token accounting (D-16): meters included credits and shows cost."""
    __tablename__ = "ai_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    review_id: Mapped[str | None] = mapped_column(ForeignKey("reviews.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80), default="")
    purpose: Mapped[str] = mapped_column(String(30), default="")           # screening | extraction
    key_source: Mapped[str] = mapped_column(String(10), default="user")    # user | server
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)


class ActivityLog(Base):
    """What happened in a review, for the overview feed."""
    __tablename__ = "activity_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)
