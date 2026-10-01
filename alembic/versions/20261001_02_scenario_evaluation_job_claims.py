"""Add fenced claim and lease state for scenario-evaluation jobs.

Revision ID: 20261001_02
Revises: 20261001_01
Create Date: 2026-10-01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261001_02"
down_revision = "20261001_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenario_evaluation_jobs",
        sa.Column("claim_token", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "scenario_evaluation_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scenario_evaluation_jobs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scenario_evaluation_jobs",
        sa.Column("failure_code", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "scenario_evaluation_jobs",
        sa.Column("failure_detail", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_scenario_evaluation_jobs_claim_token",
        "scenario_evaluation_jobs",
        ["claim_token"],
    )
    op.create_index(
        "ix_scenario_evaluation_jobs_lease_expires_at",
        "scenario_evaluation_jobs",
        ["lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scenario_evaluation_jobs_lease_expires_at", table_name="scenario_evaluation_jobs"
    )
    op.drop_index("ix_scenario_evaluation_jobs_claim_token", table_name="scenario_evaluation_jobs")
    op.drop_column("scenario_evaluation_jobs", "failure_detail")
    op.drop_column("scenario_evaluation_jobs", "failure_code")
    op.drop_column("scenario_evaluation_jobs", "attempt_count")
    op.drop_column("scenario_evaluation_jobs", "lease_expires_at")
    op.drop_column("scenario_evaluation_jobs", "claim_token")
