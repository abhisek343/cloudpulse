"""
CloudPulse AI - Cost Service
Shared fallback implementations for cost providers.
"""
from datetime import datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.services.providers.base import CostProvider


async def chronos_forecast_fallback(
    provider: CostProvider,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """
    Fallback implementation that fetches recent cost data from the provider
    and delegates the prediction to the ML service (Amazon Chronos).
    """
    settings = get_settings()
    
    # We need historical context for Chronos (at least 30 days)
    # So we fetch historical data from start_date minus min_samples_for_training days
    history_start = start_date - timedelta(days=settings.min_samples_for_training)
    
    try:
        # Fetch the historical data using the provider's own get_cost_data method
        historical_costs = await provider.get_cost_data(
            start_date=history_start,
            end_date=start_date,
            granularity="DAILY"
        )
        
        # Format for ML service
        cost_data = [
            {
                "date": record["date"].isoformat() if isinstance(record["date"], datetime) else record["date"],
                "amount": float(record["amount"]),
                "service": record["service"],
            }
            for record in historical_costs
            if "date" in record and "amount" in record
        ]
        
        if len(cost_data) < settings.min_samples_for_training:
             return {
                 "total": 0,
                 "note": f"Insufficient historical data for fallback forecast. Needed {settings.min_samples_for_training}, got {len(cost_data)}.",
             }

        # Delegate to ML Service (we call it directly through HTTP if external or locally if internal)
        # Assuming we can just import predictor if running in same monorepo, 
        # but to keep cost-service detached from ml-service logic, we should probably call the ML API.
        # But wait, cost-predictor imports are in ml-service, so cost-service must make an HTTP call 
        # to the ml-service. The ML service URL is usually configured. Let's do a direct HTTP call.
        import httpx
        ml_url = f"{settings.ml_service_url.rstrip('/')}/ml/predict"
        
        days_to_predict = (end_date - start_date).days
        if days_to_predict <= 0:
            days_to_predict = 30 # default
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ml_url,
                json={
                    "days": days_to_predict,
                    "cost_data": cost_data,
                    "include_history": False
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
        if result.get("success"):
            predicted_total = sum(p["predicted_cost"] for p in result["predictions"])
            return {
                "total": predicted_total,
                "predictions": result["predictions"],
                "note": "Forecast generated using ML service Chronos fallback.",
            }
        else:
            return {
                "total": 0,
                "note": f"Failed to generate fallback forecast: {result.get('error')}",
            }
            
    except Exception as e:
        return {
            "total": 0,
            "note": f"Fallback forecast failed: {str(e)}",
        }
