"""
CloudPulse AI - ML Service
API endpoints for predictions and anomaly detection.
"""
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_current_user, TokenPayload
from app.core.config import get_settings
from app.core.observability import DETECTION_DURATION, PREDICTION_DURATION
from app.core.tracing import get_tracer
from app.models import (
    DetectAnomaliesRequest,
    DetectResponse,
    ModelStatus,
    PredictRequest,
    PredictResponse,
    SingleAnomalyCheckRequest,
    SingleAnomalyResponse,
    TrainRequest,
    TrainResponse,
)
from app.services import get_detector, get_predictor

router = APIRouter()
settings = get_settings()
tracer = get_tracer(__name__)


@router.post("/train", response_model=TrainResponse)
async def train_models(
    request: TrainRequest,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> TrainResponse:
    """
    Train both prediction and anomaly detection models.
    
    Requires historical cost data with at least 30 data points.
    """
    with tracer.start_as_current_span("ml.train_models") as span:
        predictor = get_predictor()
        detector = get_detector()

        cost_data = [
            {
                "date": point.date,
                "amount": float(point.amount),
                "service": point.service,
            }
            for point in request.cost_data
        ]
        span.set_attribute("cloudpulse.training.records", len(cost_data))

        predictor_result = predictor.train(cost_data)
        detector_result = detector.train(cost_data)

        success = predictor_result.get("success", False) and detector_result.get("success", False)
        span.set_attribute("cloudpulse.training.success", success)

        return TrainResponse(
            success=success,
            message="Models trained successfully" if success else "Training failed for one or more models",
            predictor_status=predictor_result,
            detector_status=detector_result,
        )


@router.post("/predict", response_model=PredictResponse)
async def predict_costs(
    request: PredictRequest,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> PredictResponse:
    """
    Predict future costs for the specified number of days.
    
    Returns predictions with confidence intervals.
    """
    predictor = get_predictor()
    started_at = time.perf_counter()

    with tracer.start_as_current_span("ml.predict_costs") as span:
        cost_data = [
            {
                "date": point.date,
                "amount": float(point.amount),
                "service": point.service,
            }
            for point in request.cost_data
        ]
        span.set_attribute("cloudpulse.prediction.records", len(cost_data))
        span.set_attribute("cloudpulse.prediction.days", request.days)

        result = await predictor.predict(
            days=request.days,
            include_history=request.include_history,
            cost_data=cost_data,
        )

        if not result.get("success"):
            span.set_attribute("cloudpulse.prediction.success", False)
            PREDICTION_DURATION.labels(status="failed").observe(time.perf_counter() - started_at)
            return PredictResponse(
                success=False,
                error=result.get("error", "Prediction failed"),
            )
        span.set_attribute("cloudpulse.prediction.success", True)
        PREDICTION_DURATION.labels(status="success").observe(time.perf_counter() - started_at)

        return PredictResponse(
            success=True,
            predictions=result["predictions"],
            summary=result["summary"],
        )


@router.post("/detect", response_model=DetectResponse)
async def detect_anomalies(
    request: DetectAnomaliesRequest,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> DetectResponse:
    """
    Detect anomalies in the provided cost data.
    
    If model is not trained, trains on the provided data first.
    """
    detector = get_detector()
    started_at = time.perf_counter()

    with tracer.start_as_current_span("ml.detect_anomalies") as span:
        cost_data = [
            {
                "date": point.date,
                "amount": float(point.amount),
                "service": point.service,
            }
            for point in request.cost_data
        ]
        span.set_attribute("cloudpulse.detection.records", len(cost_data))

        if not detector.is_fitted:
            train_result = detector.train(cost_data)
            if not train_result.get("success"):
                span.set_attribute("cloudpulse.detection.success", False)
                DETECTION_DURATION.labels(status="failed").observe(time.perf_counter() - started_at)
                return DetectResponse(
                    success=False,
                    error=train_result.get("error", "Failed to train detector"),
                )

        result = detector.detect(cost_data)

        if not result.get("success"):
            span.set_attribute("cloudpulse.detection.success", False)
            DETECTION_DURATION.labels(status="failed").observe(time.perf_counter() - started_at)
            return DetectResponse(
                success=False,
                error=result.get("error", "Detection failed"),
            )
        span.set_attribute("cloudpulse.detection.success", True)
        span.set_attribute("cloudpulse.detection.anomalies_found", result["anomalies_found"])
        DETECTION_DURATION.labels(status="success").observe(time.perf_counter() - started_at)

        return DetectResponse(
            success=True,
            total_records=result["total_records"],
            anomalies_found=result["anomalies_found"],
            anomaly_rate=result["anomaly_rate"],
            anomalies=result["anomalies"],
        )


@router.post("/detect/single", response_model=SingleAnomalyResponse)
async def check_single_anomaly(
    request: SingleAnomalyCheckRequest,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> SingleAnomalyResponse:
    """
    Quick check if a single cost record is anomalous.
    
    Uses baseline statistics for fast detection.
    """
    detector = get_detector()
    
    if not detector.is_fitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Detector not trained. Call /train or /detect endpoint first.",
        )
    
    result = detector.detect_single({
        "date": request.date,
        "amount": float(request.amount),
        "service": request.service,
    })
    
    return SingleAnomalyResponse(**result)


@router.get("/status", response_model=ModelStatus)
async def get_model_status() -> ModelStatus:
    """Get the current status of ML models."""
    predictor = get_predictor()
    detector = get_detector()
    
    return ModelStatus(
        predictor_fitted=predictor.is_fitted,
        detector_fitted=detector.is_fitted,
        predictor_last_trained=predictor.last_training_date.isoformat() if predictor.last_training_date else None,
        detector_baseline_stats=detector.baseline_stats if detector.is_fitted else None,
    )


@router.get("/trend-components")
async def get_trend_components() -> dict:
    """
    Get the trend and seasonality components from the predictor.
    
    Useful for understanding cost patterns.
    """
    with tracer.start_as_current_span("ml.get_trend_components"):
        predictor = get_predictor()

        if not predictor.is_fitted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model not trained.",
            )

        return predictor.get_trend_components()
