"""Create immutable scenario-evaluation job admission records.

Revision ID: 20261001_01
Revises:
Create Date: 2026-10-01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261001_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_evaluation_jobs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("scenario_pack_id", sa.String(length=128), nullable=False),
        sa.Column("scenario_pack_revision", sa.String(length=71), nullable=False),
        sa.Column("immutable_request_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=256), nullable=True),
        sa.Column("correlation_id", sa.String(length=256), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_scenario_job_tenant_key"),
    )
    op.create_index(
        "ix_scenario_evaluation_jobs_tenant_id", "scenario_evaluation_jobs", ["tenant_id"]
    )
    op.create_index("ix_scenario_evaluation_jobs_status", "scenario_evaluation_jobs", ["status"])
    op.create_index(
        "ix_scenario_evaluation_jobs_expires_at", "scenario_evaluation_jobs", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_scenario_evaluation_jobs_expires_at", table_name="scenario_evaluation_jobs")
    op.drop_index("ix_scenario_evaluation_jobs_status", table_name="scenario_evaluation_jobs")
    op.drop_index("ix_scenario_evaluation_jobs_tenant_id", table_name="scenario_evaluation_jobs")
    op.drop_table("scenario_evaluation_jobs")
