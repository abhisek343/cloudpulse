"""Add cloud account setup metadata and sync telemetry

Revision ID: 20260401_000002
Revises: 20260331_000001
Create Date: 2026-04-01 19:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260401_000002"
down_revision: str | None = "20260331_000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cloud_accounts", sa.Column("business_unit", sa.String(length=100), nullable=True))
    op.add_column("cloud_accounts", sa.Column("environment", sa.String(length=100), nullable=True))
    op.add_column("cloud_accounts", sa.Column("cost_center", sa.String(length=100), nullable=True))
    op.add_column(
        "cloud_accounts",
        sa.Column(
            "last_sync_status",
            sa.String(length=30),
            nullable=False,
            server_default="never_synced",
        ),
    )
    op.add_column("cloud_accounts", sa.Column("last_sync_error", sa.Text(), nullable=True))
    op.add_column(
        "cloud_accounts",
        sa.Column("last_sync_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cloud_accounts",
        sa.Column("last_sync_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cloud_accounts",
        sa.Column("last_sync_records_imported", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cloud_accounts", "last_sync_records_imported")
    op.drop_column("cloud_accounts", "last_sync_completed_at")
    op.drop_column("cloud_accounts", "last_sync_started_at")
    op.drop_column("cloud_accounts", "last_sync_error")
    op.drop_column("cloud_accounts", "last_sync_status")
    op.drop_column("cloud_accounts", "cost_center")
    op.drop_column("cloud_accounts", "environment")
    op.drop_column("cloud_accounts", "business_unit")
