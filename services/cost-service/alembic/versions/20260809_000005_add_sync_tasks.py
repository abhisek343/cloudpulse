"""Add authoritative sync task lifecycle table.

Revision ID: 20260809_000005
Revises: 20260407_000004
Create Date: 2026-08-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260809_000005"
down_revision: str | None = "20260407_000004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_tasks",
        sa.Column("id", UUID(as_uuid=False), nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cloud_account_id",
            UUID(as_uuid=False),
            sa.ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("records_imported", sa.Integer(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sync_tasks_org_queued", "sync_tasks", ["organization_id", "queued_at"])
    op.create_index("idx_sync_tasks_account_queued", "sync_tasks", ["cloud_account_id", "queued_at"])


def downgrade() -> None:
    op.drop_index("idx_sync_tasks_account_queued", table_name="sync_tasks")
    op.drop_index("idx_sync_tasks_org_queued", table_name="sync_tasks")
    op.drop_table("sync_tasks")
