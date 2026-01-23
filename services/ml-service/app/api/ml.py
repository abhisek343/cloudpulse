"""
CloudPulse AI - ML Service
API endpoints for predictions and anomaly detection.
"""
from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
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


@router.post("/train", response_model=TrainResponse)
async def train_models(request: TrainRequest) -> TrainResponse:
    """
    Train both prediction and anomaly detection models.
    
    Requires historical cost data with at least 30 data points.
    """
    predictor = get_predictor()
    detector = get_detector()
    
    # Convert to list of dicts
    cost_data = [
        {
            "date": point.date,
            "amount": float(point.amount),
            "service": point.service,
        }
        for point in request.cost_data
    ]
    
    # Train predictor
    predictor_result = predictor.train(cost_data)
    
    # Train anomaly detector
    detector_result = detector.train(cost_data)
    
    success = predictor_result.get("success", False) and detector_result.get("success", False)
    
    return TrainResponse(
        success=success,
        message="Models trained successfully" if success else "Training failed for one or more models",
        predictor_status=predictor_result,
        detector_status=detector_result,
    )


@router.post("/predict", response_model=PredictResponse)
async def predict_costs(request: PredictRequest) -> PredictResponse:
    """
    Predict future costs for the specified number of days.
    
    Returns predictions with confidence intervals.
    """
    predictor = get_predictor()
    
    if not predictor.is_fitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model not trained. Call /train endpoint first.",
        )
    
    result = predictor.predict(
        days=request.days,
        include_history=request.include_history,
    )
    
    if not result.get("success"):
        return PredictResponse(
            success=False,
            error=result.get("error", "Prediction failed"),
        )
    
    return PredictResponse(
        success=True,
        predictions=result["predictions"],
        summary=result["summary"],
    )


@router.post("/detect", response_model=DetectResponse)
async def detect_anomalies(request: DetectAnomaliesRequest) -> DetectResponse:
    """
    Detect anomalies in the provided cost data.
    
    If model is not trained, trains on the provided data first.
    """
    detector = get_detector()
    
    # Convert to list of dicts
    cost_data = [
        {
            "date": point.date,
            "amount": float(point.amount),
            "service": point.service,
        }
        for point in request.cost_data
    ]
    
    # Train if not already fitted
    if not detector.is_fitted:
        train_result = detector.train(cost_data)
        if not train_result.get("success"):
            return DetectResponse(
                success=False,
                error=train_result.get("error", "Failed to train detector"),
            )
    
    # Detect anomalies
    result = detector.detect(cost_data)
    
    if not result.get("success"):
        return DetectResponse(
            success=False,
            error=result.get("error", "Detection failed"),
        )
    
    return DetectResponse(
        success=True,
        total_records=result["total_records"],
        anomalies_found=result["anomalies_found"],
        anomaly_rate=result["anomaly_rate"],
        anomalies=result["anomalies"],
    )


@router.post("/detect/single", response_model=SingleAnomalyResponse)
async def check_single_anomaly(request: SingleAnomalyCheckRequest) -> SingleAnomalyResponse:
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
    predictor = get_predictor()
    
    if not predictor.is_fitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model not trained.",
        )
    
    return predictor.get_trend_components()
