from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String, Text, UniqueConstraint
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
    submitted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
