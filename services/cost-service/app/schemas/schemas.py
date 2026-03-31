"""
CloudPulse AI - Cost Service
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# === Enums ===


class CloudProvider(StrEnum):
    DEMO = "demo"
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class CostGranularity(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


# === Base Schemas ===


class BaseSchema(BaseModel):
    """Base schema with common config."""

    model_config = ConfigDict(from_attributes=True)


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: datetime | None = None


# === Organization Schemas ===


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


class OrganizationResponse(BaseSchema, TimestampMixin):
    id: str
    name: str
    slug: str
    is_active: bool


# === User Schemas ===


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="member")


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(None, min_length=1, max_length=255)
    role: str | None = None
    is_active: bool | None = None


class UserResponse(BaseSchema, TimestampMixin):
    id: str
    organization_id: str
    email: str
    full_name: str
    role: str
    is_active: bool


# === Cloud Account Schemas ===


class CloudAccountCreate(BaseModel):
    provider: CloudProvider
    account_id: str = Field(..., min_length=1, max_length=100)
    account_name: str = Field(..., min_length=1, max_length=255)
    credentials: dict | None = None


class CloudAccountUpdate(BaseModel):
    account_name: str | None = Field(None, min_length=1, max_length=255)
    credentials: dict | None = None
    is_active: bool | None = None


class CloudAccountResponse(BaseSchema):
    id: str
    organization_id: str
    provider: str
    account_id: str
    account_name: str
    is_active: bool
    last_sync_at: datetime | None
    created_at: datetime


# === Cost Record Schemas ===


class CostRecordCreate(BaseModel):
    date: datetime
    granularity: CostGranularity
    service: str
    region: str | None = None
    resource_id: str | None = None
    amount: Decimal
    currency: str = "USD"
    tags: dict | None = None
    metadata: dict | None = None


class CostRecordResponse(BaseSchema):
    id: str
    cloud_account_id: str
    date: datetime
    granularity: str
    service: str
    region: str | None
    resource_id: str | None
    amount: Decimal
    currency: str
    tags: dict | None
    created_at: datetime


class CostSummary(BaseModel):
    """Aggregated cost summary."""

    total_cost: Decimal
    currency: str = "USD"
    period_start: datetime
    period_end: datetime
    by_service: dict[str, Decimal] = Field(default_factory=dict)
    by_region: dict[str, Decimal] = Field(default_factory=dict)
    by_day: list[dict] = Field(default_factory=list)


class CostTrend(BaseModel):
    """Cost trend data for visualization."""

    date: datetime
    amount: Decimal
    change_percent: Decimal | None = None
    predicted: bool = False


# === Budget Schemas ===


class BudgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    amount: Decimal = Field(..., gt=0)
    currency: str = "USD"
    period: str = Field(default="monthly", pattern=r"^(monthly|quarterly|yearly)$")
    filters: dict | None = None
    alert_thresholds: list[int] = Field(default=[50, 80, 100])


class BudgetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    amount: Decimal | None = Field(None, gt=0)
    filters: dict | None = None
    alert_thresholds: list[int] | None = None
    is_active: bool | None = None


class BudgetResponse(BaseSchema, TimestampMixin):
    id: str
    organization_id: str
    name: str
    description: str | None
    amount: Decimal
    currency: str
    period: str
    filters: dict | None
    alert_thresholds: list[int]
    is_active: bool


class BudgetStatus(BaseModel):
    """Current budget status with usage."""

    budget: BudgetResponse
    current_spend: Decimal
    usage_percent: Decimal
    remaining: Decimal
    forecast_end_of_period: Decimal | None = None
    alerts_triggered: list[int] = Field(default_factory=list)


# === Anomaly Schemas ===


class CostAnomalyResponse(BaseSchema):
    id: str
    cloud_account_id: str
    detected_at: datetime
    anomaly_date: datetime
    service: str
    region: str | None
    expected_amount: Decimal
    actual_amount: Decimal
    deviation_percent: Decimal
    severity: str
    status: str
    root_cause: str | None
    recommendations: list[str] | None
    resolved_at: datetime | None
    created_at: datetime


class AnomalyUpdateStatus(BaseModel):
    status: AnomalyStatus
    root_cause: str | None = None


# === API Response Wrappers ===


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthCheck(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    database: str = "connected"
    redis: str = "connected"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RuntimeProviderStatus(BaseModel):
    """Provider readiness snapshot for the runtime status endpoint."""

    configured: bool
    readiness: str
    note: str


class RuntimeStatus(BaseModel):
    """Current runtime mode and provider readiness details."""

    environment: str
    cloud_sync_mode: str
    allow_live_cloud_sync: bool
    default_demo_provider: str
    default_demo_scenario: str
    llm_provider: str
    llm_configured: bool
    providers: dict[str, RuntimeProviderStatus]


class ProviderPreflightCheck(BaseModel):
    """Individual check in the provider preflight response."""

    name: str
    status: str
    detail: str


class ProviderPreflightResult(BaseModel):
    """Live-provider preflight summary for OSS operators."""

    provider: str
    configured: bool
    ready: bool
    credential_source: str
    cost_source: str
    missing_env: list[str] = Field(default_factory=list)
    checks: list[ProviderPreflightCheck] = Field(default_factory=list)
