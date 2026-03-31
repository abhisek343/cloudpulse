"""
CloudPulse AI - ML Service
Configuration and settings.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_JWT_SECRET = "cloudpulse-dev-shared-secret-change-in-production"


class Settings(BaseSettings):
    """ML Service settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = "CloudPulse AI - ML Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    
    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3005"]
    )
    
    # Cost Service URL (for fetching data)
    cost_service_url: str = "http://localhost:8001"
    
    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/1")
    
    # RabbitMQ
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    
    # ML Settings
    model_path: str = "./models"
    prediction_confidence_threshold: float = 0.8
    anomaly_sensitivity: Literal["low", "medium", "high"] = "medium"
    forecast_days: int = 30
    min_samples_for_training: int = 14
    chronos_model_size: Literal["tiny", "small", "base", "large"] = "tiny"
    
    # JWT Authentication (for verifying tokens from frontend)
    jwt_secret_key: str = Field(default=DEFAULT_DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    
    # Anomaly Detection Settings
    anomaly_contamination: float = 0.1  # Expected proportion of outliers

    # Distributed tracing
    otel_enabled: bool = False
    otel_service_name: str = "cloudpulse-ml-service"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_insecure: bool = True
    otel_sampler_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    otel_excluded_urls: str = "/health,/metrics"

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
