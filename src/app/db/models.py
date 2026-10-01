from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScenarioEvaluationJobModel(Base):
    __tablename__ = "scenario_evaluation_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_scenario_job_tenant_key"),
    )

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    scenario_pack_id: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_pack_revision: Mapped[str] = mapped_column(String(71), nullable=False)
    immutable_request_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    lease_expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ScenarioEvaluationJobContributionModel(Base):
    __tablename__ = "scenario_evaluation_job_contributions"
    __table_args__ = (
        UniqueConstraint(
            "job_id", "scenario_id", "ordinal", name="uq_scenario_job_contribution_ordinal"
        ),
    )

    job_id: Mapped[str] = mapped_column(
        ForeignKey("scenario_evaluation_jobs.job_id", ondelete="CASCADE"), primary_key=True
    )
    scenario_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    security_id: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    weight: Mapped[float] = mapped_column(nullable=False)
    shock_pct: Mapped[float] = mapped_column(nullable=False)
    contribution_loss_pct: Mapped[float] = mapped_column(nullable=False)
