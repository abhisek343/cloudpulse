"""
CloudPulse AI - Cost Service
Database models for cost data storage.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CloudProvider(str, Enum):
    """Supported cloud providers."""
    DEMO = "demo"
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class CostGranularity(str, Enum):
    """Cost data granularity."""
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class Organization(Base):
    """Organization/tenant model for multi-tenancy."""
    
    __tablename__ = "organizations"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    cloud_accounts: Mapped[list["CloudAccount"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class User(Base):
    """User model."""
    
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")
    
    __table_args__ = (
        Index("idx_users_org_email", "organization_id", "email"),
    )


class CloudAccount(Base):
    """Cloud provider account configuration."""
    
    __tablename__ = "cloud_accounts"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credentials: Mapped[dict] = mapped_column(JSONB, nullable=True)  # Optional per-account overrides
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="cloud_accounts")
    cost_records: Mapped[list["CostRecord"]] = relationship(
        back_populates="cloud_account",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        Index("idx_cloud_accounts_org", "organization_id"),
        Index("idx_cloud_accounts_provider", "provider", "account_id"),
    )


class CostRecord(Base):
    """Individual cost record from cloud provider."""
    
    __tablename__ = "cost_records"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    cloud_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
    )
    
    # Time dimensions
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granularity: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Cost dimensions
    service: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(500))
    
    # Cost values
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    
    # Tags and metadata
    tags: Mapped[dict | None] = mapped_column(JSONB)
    record_metadata: Mapped[dict | None] = mapped_column(JSONB)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    cloud_account: Mapped["CloudAccount"] = relationship(back_populates="cost_records")
    
    __table_args__ = (
        Index("idx_cost_records_date", "cloud_account_id", "date"),
        Index("idx_cost_records_service", "cloud_account_id", "service", "date"),
        Index("idx_cost_records_tags", "tags", postgresql_using="gin"),
    )


class Budget(Base):
    """Budget configuration and tracking."""
    
    __tablename__ = "budgets"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Budget configuration
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    period: Mapped[str] = mapped_column(String(20), default="monthly")  # monthly, quarterly, yearly
    
    # Filters
    filters: Mapped[dict | None] = mapped_column(JSONB)  # service, region, tags
    
    # Alert thresholds (percentages)
    alert_thresholds: Mapped[list] = mapped_column(
        JSONB,
        default=lambda: [50, 80, 100],
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    __table_args__ = (
        Index("idx_budgets_org", "organization_id"),
    )


class CostAnomaly(Base):
    """Detected cost anomalies."""
    
    __tablename__ = "cost_anomalies"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    cloud_account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
    )
    
    # Anomaly details
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    anomaly_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    
    # Values
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    deviation_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    
    # Severity: low, medium, high, critical
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Status: open, acknowledged, resolved, false_positive
    status: Mapped[str] = mapped_column(String(20), default="open")
    
    # Analysis
    root_cause: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[list | None] = mapped_column(JSONB)
    
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    __table_args__ = (
        Index("idx_anomalies_account_date", "cloud_account_id", "anomaly_date"),
        Index("idx_anomalies_status", "status", "severity"),
    )


class AuditLog(Base):
    """Audit log for tracking user actions and system events."""
    
    __tablename__ = "audit_logs"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    
    # Action details
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # LOGIN, CREATE, UPDATE, DELETE, SYNC
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # auth, cloud_account, budget
    resource_id: Mapped[str | None] = mapped_column(String(100))
    
    # Metadata
    details: Mapped[dict | None] = mapped_column(JSONB)  # IP, User Agent, Changes
    ip_address: Mapped[str | None] = mapped_column(String(45))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    user: Mapped["User"] = relationship()
    
    __table_args__ = (
        Index("idx_audit_logs_org_created", "organization_id", "created_at"),
        Index("idx_audit_logs_user", "user_id"),
    )
