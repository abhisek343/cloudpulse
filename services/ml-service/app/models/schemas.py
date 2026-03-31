"""
CloudPulse AI - ML Service
Pydantic schemas for API validation.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# === Request Schemas ===

class CostDataPoint(BaseModel):
    """Single cost data point for training/prediction."""
    date: datetime
    amount: Decimal = Field(..., ge=0)
    service: str | None = None
    region: str | None = None


class TrainRequest(BaseModel):
    """Request to train ML models."""
    cost_data: list[CostDataPoint] = Field(..., min_length=1)
    retrain: bool = False


class PredictRequest(BaseModel):
    """Request for cost prediction."""
    days: int = Field(default=30, ge=1, le=365)
    include_history: bool = False
    cost_data: list[CostDataPoint] = Field(..., min_length=1)


class DetectAnomaliesRequest(BaseModel):
    """Request for anomaly detection."""
    cost_data: list[CostDataPoint] = Field(..., min_length=1)


class SingleAnomalyCheckRequest(BaseModel):
    """Request to check single record for anomaly."""
    date: datetime
    amount: Decimal = Field(..., ge=0)
    service: str | None = None


# === Response Schemas ===

class TrainResponse(BaseModel):
    """Response from training endpoint."""
    success: bool
    message: str
    predictor_status: dict | None = None
    detector_status: dict | None = None


class PredictionPoint(BaseModel):
    """Single prediction point."""
    date: str
    predicted_cost: float
    lower_bound: float
    upper_bound: float


class PredictionSummary(BaseModel):
    """Summary of predictions."""
    total_predicted_cost: float
    average_daily_cost: float
    forecast_days: int
    confidence_level: float


class PredictResponse(BaseModel):
    """Response from prediction endpoint."""
    success: bool
    predictions: list[PredictionPoint] = []
    summary: PredictionSummary | None = None
    error: str | None = None


class AnomalyRecord(BaseModel):
    """Single anomaly record."""
    date: str
    actual_cost: float
    expected_cost: float
    deviation_percent: float
    severity: Literal["low", "medium", "high", "critical"]
    anomaly_score: float
    service: str | None = None


class DetectResponse(BaseModel):
    """Response from anomaly detection."""
    success: bool
    total_records: int = 0
    anomalies_found: int = 0
    anomaly_rate: float = 0
    anomalies: list[AnomalyRecord] = []
    error: str | None = None


class SingleAnomalyResponse(BaseModel):
    """Response for single anomaly check."""
    is_anomaly: bool
    severity: Literal["low", "medium", "high", "critical"] | None = None
    z_score: float
    amount: float
    baseline_mean: float
    baseline_std: float


class ModelStatus(BaseModel):
    """Status of ML models."""
    predictor_fitted: bool
    detector_fitted: bool
    predictor_last_trained: str | None = None
    detector_baseline_stats: dict | None = None


class HealthCheck(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    models_ready: bool = False
