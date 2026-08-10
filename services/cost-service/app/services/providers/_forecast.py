"""
CloudPulse AI - Cost Service
Shared fallback implementations for cost providers.
"""
from datetime import datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.core.logging import sanitize_error
from app.services.currency import normalize_currency
from app.services.providers.base import CostProvider


async def chronos_forecast_fallback(
    provider: CostProvider,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """Fetch provider history and call the authenticated ML forecast endpoint."""
    settings = get_settings()
    history_start = start_date - timedelta(days=settings.min_samples_for_training)
    organization_id = getattr(provider, "organization_id", None)

    if not settings.internal_service_token or not organization_id:
        return {
            "total": 0,
            "note": "Fallback forecast unavailable because authenticated ML service configuration is incomplete.",
        }

    try:
        historical_costs = await provider.get_cost_data(
            start_date=history_start,
            end_date=start_date,
            granularity="DAILY",
        )
        try:
            currencies = {
                normalize_currency(record.get("currency"))
                for record in historical_costs
                if "date" in record and "amount" in record
            }
        except ValueError:
            return {
                "total": 0,
                "note": "Fallback forecast requires valid currency data.",
            }
        if len(currencies) > 1:
            return {
                "total": 0,
                "note": "Fallback forecast requires one currency at a time.",
            }
        currency = next(iter(currencies), None)
        if currency is None:
            return {"total": 0, "note": "Fallback forecast has no usable cost data."}
        cost_data = [
            {
                "date": (
                    record["date"].isoformat()
                    if isinstance(record["date"], datetime)
                    else record["date"]
                ),
                "amount": float(record["amount"]),
                "currency": currency,
                "service": record.get("service"),
            }
            for record in historical_costs
            if "date" in record and "amount" in record
        ]

        if len(cost_data) < settings.min_samples_for_training:
            return {
                "total": 0,
                "note": (
                    "Insufficient historical data for fallback forecast. "
                    f"Needed {settings.min_samples_for_training}, got {len(cost_data)}."
                ),
            }

        import httpx

        ml_url = f"{settings.ml_service_url.rstrip('/')}/api/v1/ml/predict"
        days_to_predict = max((end_date - start_date).days, 1)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                ml_url,
                headers={
                    "X-Internal-Service-Token": settings.internal_service_token,
                    "X-Organization-ID": str(organization_id),
                },
                json={
                    "days": days_to_predict,
                    "cost_data": cost_data,
                    "include_history": False,
                },
            )
            response.raise_for_status()
            result = response.json()

        if result.get("success"):
            predicted_total = sum(
                prediction["predicted_cost"] for prediction in result["predictions"]
            )
            return {
                "total": predicted_total,
                "predictions": result["predictions"],
                "currency": currency,
                "note": "Forecast generated using the authenticated ML service fallback.",
            }
        return {
            "total": 0,
            "note": f"Fallback forecast unavailable: {sanitize_error(ValueError(str(result.get('error', 'unknown error'))))}",
        }
    except Exception as exc:
        return {
            "total": 0,
            "note": f"Fallback forecast failed: {sanitize_error(exc)}",
        }
