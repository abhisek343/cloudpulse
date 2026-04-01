"""
CloudPulse AI - Cost Service
Core configuration and settings management.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_JWT_SECRET = "cloudpulse-dev-shared-secret-change-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = "CloudPulse AI - Cost Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    
    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3005"]
    )
    csrf_trusted_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3005"]
    )
    
    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cloudpulse"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    
    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_cache_ttl: int = 300  # 5 minutes
    
    # RabbitMQ
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    
    # AWS
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    aws_session_token: str | None = None

    # Azure
    azure_subscription_id: str | None = None
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None

    # GCP
    gcp_project_id: str | None = None
    gcp_billing_account_id: str | None = None
    gcp_service_account_json: str | None = None
    gcp_service_account_file: str | None = None
    gcp_billing_export_table: str | None = None

    # Sync / Demo mode
    cloud_sync_mode: Literal["demo", "live"] = "demo"
    allow_live_cloud_sync: bool = False
    default_demo_scenario: Literal["saas", "startup", "enterprise", "incident"] = "saas"
    default_demo_seed: int = 42
    default_demo_provider: Literal["aws", "azure", "gcp"] = "aws"

    # LLM
    llm_provider: str = "openrouter"  # openrouter, openai, anthropic, gemini, ollama
    llm_api_key: str | None = None
    llm_model: str = "openrouter/free"
    llm_base_url: str | None = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 60.0
    llm_fallback_models: list[str] = Field(
        default_factory=lambda: [
            "stepfun/step-3.5-flash:free",
            "nvidia/nemotron-3-super-120b-a12b-20230311:free",
        ]
    )
    
    # Kubernetes / Prometheus
    prometheus_url: str = "http://prometheus-server:9090"
    
    # Kubernetes Cost Estimation
    k8s_cpu_hourly_rate: float = 0.04  # $ per vCPU hour
    k8s_memory_hourly_rate: float = 0.004  # $ per GB hour
    
    # JWT Authentication
    jwt_secret_key: str = Field(default=DEFAULT_DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "cloudpulse_refresh_token"
    csrf_cookie_name: str = "cloudpulse_csrf_token"
    auth_cookie_secure: bool = False

    # Account credentials
    account_credentials_key: str | None = None
    
    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: str | None) -> str:
        """Ensure JWT secret is explicit in production and shared in development."""
        if not v:
            return DEFAULT_DEV_JWT_SECRET

        if v == DEFAULT_DEV_JWT_SECRET:
            return v

        if v == "change-me-in-production":
            raise ValueError("JWT_SECRET_KEY must not use the placeholder value")

        return v

    @model_validator(mode="after")
    def validate_runtime_security(self) -> "Settings":
        """Require safer runtime defaults outside local development."""
        if self.environment != "production":
            return self

        if self.jwt_secret_key == DEFAULT_DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be set to a unique value in production")

        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")

        if self.debug:
            raise ValueError("DEBUG must be disabled in production")

        return self
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 300
    enable_startup_migrations: bool = True

    # Distributed tracing
    otel_enabled: bool = False
    otel_service_name: str = "cloudpulse-cost-service"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_insecure: bool = True
    otel_sampler_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    otel_excluded_urls: str = "/health,/metrics"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
