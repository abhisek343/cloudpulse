"""
CloudPulse AI - Cost Service
Core configuration and settings management.
"""
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    
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

    # LLM
    llm_provider: str = "openai"  # openai, anthropic, gemini, ollama
    llm_api_key: str | None = None
    llm_model: str = "gpt-3.5-turbo"
    llm_base_url: str | None = None  # For Ollama / compatible APIs
    
    # Kubernetes / Prometheus
    prometheus_url: str = "http://prometheus-server:9090"
    
    # Kubernetes Cost Estimation
    k8s_cpu_hourly_rate: float = 0.04  # $ per vCPU hour
    k8s_memory_hourly_rate: float = 0.004  # $ per GB hour
    
    # JWT Authentication
    jwt_secret_key: str = Field(default=...)  # Required - no default
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: str | None) -> str:
        """Ensure JWT secret is set and not the placeholder value."""
        if not v or v == "change-me-in-production":
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise ValueError("JWT_SECRET_KEY must be set in production")
            # For development, generate a random key
            import secrets
            return secrets.token_urlsafe(32)
        return v
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
