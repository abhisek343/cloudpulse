"""Initial schema

Revision ID: 20260331_000001
Revises:
Create Date: 2026-03-31 18:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260331_000001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_users_org_email", "users", ["organization_id", "email"], unique=False)

    op.create_table(
        "cloud_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("account_id", sa.String(length=100), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("credentials", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cloud_accounts_org", "cloud_accounts", ["organization_id"], unique=False)
    op.create_index("idx_cloud_accounts_provider", "cloud_accounts", ["provider", "account_id"], unique=False)

    op.create_table(
        "cost_records",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("cloud_account_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granularity", sa.String(length=20), nullable=False),
        sa.Column("service", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=500), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("record_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["cloud_account_id"], ["cloud_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cost_records_date", "cost_records", ["cloud_account_id", "date"], unique=False)
    op.create_index(
        "idx_cost_records_service",
        "cost_records",
        ["cloud_account_id", "service", "date"],
        unique=False,
    )
    op.create_index(
        "idx_cost_records_tags",
        "cost_records",
        ["tags"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("period", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "alert_thresholds",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[50, 80, 100]'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_budgets_org", "budgets", ["organization_id"], unique=False)

    op.create_table(
        "cost_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("cloud_account_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("anomaly_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("expected_amount", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("actual_amount", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("deviation_percent", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("recommendations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["cloud_account_id"], ["cloud_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_anomalies_account_date",
        "cost_anomalies",
        ["cloud_account_id", "anomaly_date"],
        unique=False,
    )
    op.create_index("idx_anomalies_status", "cost_anomalies", ["status", "severity"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_logs_org_created", "audit_logs", ["organization_id", "created_at"], unique=False)
    op.create_index("idx_audit_logs_user", "audit_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_audit_logs_user", table_name="audit_logs")
    op.drop_index("idx_audit_logs_org_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("idx_anomalies_status", table_name="cost_anomalies")
    op.drop_index("idx_anomalies_account_date", table_name="cost_anomalies")
    op.drop_table("cost_anomalies")

    op.drop_index("idx_budgets_org", table_name="budgets")
    op.drop_table("budgets")

    op.drop_index("idx_cost_records_tags", table_name="cost_records", postgresql_using="gin")
    op.drop_index("idx_cost_records_service", table_name="cost_records")
    op.drop_index("idx_cost_records_date", table_name="cost_records")
    op.drop_table("cost_records")

    op.drop_index("idx_cloud_accounts_provider", table_name="cloud_accounts")
    op.drop_index("idx_cloud_accounts_org", table_name="cloud_accounts")
    op.drop_table("cloud_accounts")

    op.drop_index("idx_users_org_email", table_name="users")
    op.drop_table("users")

    op.drop_table("organizations")
