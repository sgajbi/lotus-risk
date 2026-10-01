"""Persist fenced scenario-job success results and contribution pages.

Revision ID: 20261001_03
Revises: 20261001_02
Create Date: 2026-10-01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261001_03"
down_revision = "20261001_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenario_evaluation_jobs", sa.Column("result_json", sa.Text(), nullable=True))
    op.add_column(
        "scenario_evaluation_jobs",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "scenario_evaluation_job_contributions",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=128), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=True),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("shock_pct", sa.Float(), nullable=False),
        sa.Column("contribution_loss_pct", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["scenario_evaluation_jobs.job_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("job_id", "scenario_id", "ordinal"),
        sa.UniqueConstraint(
            "job_id", "scenario_id", "ordinal", name="uq_scenario_job_contribution_ordinal"
        ),
    )
    op.create_index(
        "ix_scenario_job_contributions_page",
        "scenario_evaluation_job_contributions",
        ["job_id", "scenario_id", "ordinal"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scenario_job_contributions_page", table_name="scenario_evaluation_job_contributions"
    )
    op.drop_table("scenario_evaluation_job_contributions")
    op.drop_column("scenario_evaluation_jobs", "completed_at")
    op.drop_column("scenario_evaluation_jobs", "result_json")
