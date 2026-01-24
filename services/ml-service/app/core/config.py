"""
CloudPulse AI - ML Service
Configuration and settings.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    
    # Cost Service URL (for fetching data)
    cost_service_url: str = "http://localhost:8001"
    
    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/1")
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    
    # ML Settings
    model_path: str = "./models"
    prediction_confidence_threshold: float = 0.8
    anomaly_sensitivity: Literal["low", "medium", "high"] = "medium"
    forecast_days: int = 30
    min_samples_for_training: int = 14
    chronos_model_size: str = "tiny" # tiny, small, base, large
    
    # Anomaly Detection Settings
    anomaly_contamination: float = 0.1  # Expected proportion of outliers
    # min_samples_for_training: int = 30 # This line was moved to ML Settings
    


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
