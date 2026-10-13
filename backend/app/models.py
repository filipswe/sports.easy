"""Mutable source state; immutable quote, prediction, publication and settlement versions."""

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now


def uid():
    return str(uuid.uuid4())


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)


class Competition(Identity, Base):
    __tablename__ = "competitions"
    name: Mapped[str] = mapped_column(String(120))
    provider_id: Mapped[str] = mapped_column(String(80), unique=True)
    season: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(8), index=True)


class Team(Identity, Base):
    __tablename__ = "teams"
    name: Mapped[str] = mapped_column(String(120))
    provider_id: Mapped[str] = mapped_column(String(80), unique=True)


class Fixture(Identity, Base):
    __tablename__ = "fixtures"
    provider_id: Mapped[str] = mapped_column(String(100), unique=True)
    competition_id: Mapped[str] = mapped_column(ForeignKey("competitions.id"))
    home_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    away_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    kickoff: Mapped[object] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="scheduled")
    venue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_half_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_half_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_available_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_updated_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    mode: Mapped[str] = mapped_column(String(8), index=True)


class ProviderMapping(Identity, Base):
    __tablename__ = "provider_mappings"
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(200))
    entity_id: Mapped[str] = mapped_column(String(36))
    entity_type: Mapped[str] = mapped_column(String(24))
    __table_args__ = (UniqueConstraint("provider", "external_id", "entity_type"),)


class Bookmaker(Identity, Base):
    __tablename__ = "bookmakers"
    provider_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(12))


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    methodology: Mapped[dict] = mapped_column(JSON)


class Prediction(Identity, Base):
    __tablename__ = "predictions"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"))
    generated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    input_cutoff: Mapped[object] = mapped_column(DateTime(timezone=True))
    history_fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    fixture_kickoff: Mapped[object] = mapped_column(DateTime(timezone=True))
    probabilities: Mapped[dict] = mapped_column(JSON)
    factors: Mapped[dict] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    quality: Mapped[str] = mapped_column(String(24))
    mode: Mapped[str] = mapped_column(String(8), index=True)
    __table_args__ = (UniqueConstraint("fixture_id", "input_hash", "model_id"),)


class Quote(Identity, Base):
    __tablename__ = "quotes"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"), index=True)
    bookmaker_id: Mapped[str] = mapped_column(ForeignKey("bookmakers.id"))
    market: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(16))
    price: Mapped[object] = mapped_column(Numeric(10, 4))
    snapshot_key: Mapped[str] = mapped_column(String(64))
    source_updated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    mode: Mapped[str] = mapped_column(String(8), index=True)
    __table_args__ = (
        UniqueConstraint("fixture_id", "bookmaker_id", "snapshot_key", "market", "outcome"),
        Index("ix_quote_lookup", "fixture_id", "market", "outcome", "fetched_at"),
    )


class Publication(Identity, Base):
    __tablename__ = "publications"
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id"))
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("prediction_id", "quote_id"),)


class Settlement(Identity, Base):
    __tablename__ = "settlements"
    publication_id: Mapped[str] = mapped_column(ForeignKey("publications.id"), index=True)
    result: Mapped[str] = mapped_column(String(24))
    result_signature: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(String(200))
    recorded_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("settlements.id"), nullable=True)
    __table_args__ = (UniqueConstraint("publication_id", "result_signature"),)


class Recommendation(Identity, Base):
    __tablename__ = "recommendations"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"), unique=True)
    publication_id: Mapped[str] = mapped_column(ForeignKey("publications.id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    policy: Mapped[str] = mapped_column(String(80), default="top-probability-distinct-fixtures-v1")


class EvaluationRun(Identity, Base):
    __tablename__ = "evaluation_runs"
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    mode: Mapped[str] = mapped_column(String(8))
    model_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"))
    report: Mapped[dict] = mapped_column(JSON)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    admin: Mapped[bool] = mapped_column(Boolean, default=False)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))


class SavedSelection(Identity, Base):
    __tablename__ = "saved_selections"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    publication_id: Mapped[str] = mapped_column(ForeignKey("publications.id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("user_id", "publication_id"),)


class Job(Identity, Base):
    __tablename__ = "jobs"
    key: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class IngestionRun(Identity, Base):
    __tablename__ = "ingestion_runs"
    provider: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now, index=True)
    status: Mapped[str] = mapped_column(String(24))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class AdminAudit(Identity, Base):
    __tablename__ = "admin_audit"
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


# In addition to application policy, PostgreSQL migration installs immutable-table triggers.
for immutable in (Prediction, Quote, Publication, Settlement, EvaluationRun, Recommendation):

    @event.listens_for(immutable, "before_update")
    @event.listens_for(immutable, "before_delete")
    def reject_change(mapper, connection, target):
        raise ValueError("Published research is append-only; create a revision")
