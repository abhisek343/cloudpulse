"""add notification_channels table

Revision ID: 20260407_000004
Revises: 20260407_000003
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "20260407_000004"
down_revision = "20260407_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("events", JSONB, nullable=False, server_default='["anomaly","budget"]'),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_notification_channels_org",
        "notification_channels",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_notification_channels_org", table_name="notification_channels")
    op.drop_table("notification_channels")
