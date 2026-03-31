"""
CloudPulse AI - ML Service
Cost prediction using Amazon Chronos (Foundation Model).
"""
import asyncio
import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
import pandas as pd
from app.core.config import get_settings

if TYPE_CHECKING:
    from chronos import ChronosPipeline

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "Torch is not installed. Install the ML service with the 'inference' extra."
        ) from exc

    return torch


class CostPredictor:
    """
    Cost prediction service using Amazon Chronos (T5-based Time Series Foundation Model).
    
    Chronos performs zero-shot forecasting, meaning it doesn't need to be 'trained'
    on specific datasets in the traditional sense, but infers patterns from context.
    """
    
    def __init__(self) -> None:
        self.pipeline: Optional["ChronosPipeline"] = None
        try:
            torch = _get_torch()
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        except RuntimeError:
            self.device = "cpu"
        self.model_name = f"amazon/chronos-t5-{settings.chronos_model_size}"
        self._last_training_date: Optional[datetime] = None
    
    @property
    def is_fitted(self) -> bool:
        """Check if model is loaded and ready for predictions."""
        return self.pipeline is not None
    
    @property
    def last_training_date(self) -> Optional[datetime]:
        """Get the last training/initialization date."""
        return self._last_training_date
        
    def _load_model(self) -> None:
        """Lazy load the heavy model."""
        if self.pipeline is None:
            try:
                from chronos import ChronosPipeline
            except ImportError as exc:
                raise RuntimeError(
                    "Chronos is not installed. Install the ML service with the 'inference' extra."
                ) from exc
            torch = _get_torch()

            logger.info(f"Loading Chronos model: {self.model_name} on {self.device}...")
            self.pipeline = ChronosPipeline.from_pretrained(
                self.model_name,
                device_map=self.device,
                torch_dtype=torch.bfloat16,
            )
            logger.info("Chronos model loaded successfully.")

    def prepare_data(self, cost_data: list[dict[str, Any]]) -> Any:
        """
        Prepare cost data for Chronos.
        Returns a torch Tensor when torch is installed, otherwise a numpy array.
        """
        df = pd.DataFrame(cost_data)
        
        if "date" not in df.columns or "amount" not in df.columns:
            raise ValueError("Data must contain 'date' and 'amount' columns")
            
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # Aggregate duplicates (in case of multiple entries per day)
        df = df.groupby("date")["amount"].sum().reset_index()
        
        # Fill missing dates with 0
        date_range = pd.date_range(start=df["date"].min(), end=df["date"].max(), freq="D")
        df = df.set_index("date").reindex(date_range).fillna(0)
        
        values = df["amount"].to_numpy(dtype=np.float32)

        try:
            torch = _get_torch()
        except RuntimeError:
            return values

        return torch.tensor(values, dtype=torch.float32)

    def train(self, cost_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        'Train' method for compatibility. 
        For Foundation Models, this just validates data and pre-loads weights.
        """
        if len(cost_data) < settings.min_samples_for_training:
            return {
                "success": False,
                "error": f"Insufficient context. Need at least {settings.min_samples_for_training} days.",
            }
            
        try:
            self._load_model()
            # Verify data format
            _ = self.prepare_data(cost_data)
            self._last_training_date = datetime.now(timezone.utc)
            
            return {
                "success": True,
                "model": self.model_name,
                "status": "Ready (Zero-Shot)",
                "trained_at": self._last_training_date.isoformat(),
            }
        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            return {"success": False, "error": str(e)}

    def _predict_with_pipeline(self, context_tensor: Any, days: int) -> Any:
        """Call Chronos using the installed API shape."""
        if self.pipeline is None:
            raise RuntimeError("Chronos pipeline is not loaded")

        predict_signature = inspect.signature(self.pipeline.predict)
        predict_kwargs: dict[str, Any] = {
            "prediction_length": days,
            "num_samples": 20,
        }

        if "inputs" in predict_signature.parameters:
            predict_kwargs["inputs"] = context_tensor
        else:
            predict_kwargs["context"] = context_tensor

        return self.pipeline.predict(**predict_kwargs)

    async def predict(
        self,
        days: int | None = None,
        include_history: bool = False,
        cost_data: Optional[list[dict[str, Any]]] = None, # Passed dynamically for context
    ) -> dict[str, Any]:
        """
        Generate cost predictions.
        
        Args:
            days: Forecast horizon
            cost_data: Historical context is REQUIRED for zero-shot inference
        """
        if not cost_data:
             return {"success": False, "error": "Chronos requires 'cost_data' context for inference."}

        days = days or settings.forecast_days
        self._load_model()
        
        try:
            # 1. Prepare Context
            context_tensor = self.prepare_data(cost_data)
            
            # 2. Generate Forecast - Run in thread to avoid blocking event loop
            # Chronos expects list of contexts. We have 1 series.
            # num_samples=20 allows us to compute confidence intervals
            forecast = await asyncio.to_thread(
                self._predict_with_pipeline,
                context_tensor,
                days,
            )
            # forecast shape: (1, num_samples, prediction_length)
            
            # 3. Process Results
            # Compute median and quantiles
            forecast_tensor = forecast[0] # (num_samples, days)
            torch = _get_torch()
            median = torch.median(forecast_tensor, dim=0).values.numpy()
            lower = torch.quantile(forecast_tensor, 0.1, dim=0).numpy()
            upper = torch.quantile(forecast_tensor, 0.9, dim=0).numpy()
            
            # 4. Map dates - handle various date formats
            raw_date = cost_data[-1]["date"]
            if isinstance(raw_date, datetime):
                last_date = raw_date
            elif isinstance(raw_date, str):
                try:
                    last_date = datetime.strptime(raw_date, "%Y-%m-%d")
                except ValueError:
                    last_date = datetime.fromisoformat(raw_date)
            else:
                last_date = datetime.now(timezone.utc)

            future_dates = [last_date + timedelta(days=i+1) for i in range(days)]
            
            result = []
            for i, date in enumerate(future_dates):
                result.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_cost": float(max(0, median[i])),
                    "lower_bound": float(max(0, lower[i])),
                    "upper_bound": float(max(0, upper[i])),
                })
            
            # Summary
            total_predicted = sum(r["predicted_cost"] for r in result)
            average_daily = total_predicted / days if days else 0
            
            return {
                "success": True,
                "predictions": result,
                "summary": {
                    "total_predicted_cost": round(total_predicted, 2),
                    "average_daily_cost": round(average_daily, 2),
                    "forecast_days": days,
                    "confidence_level": settings.prediction_confidence_threshold,
                },
            }
            
        except Exception as e:
            logger.error(f"Chronos Prediction failed: {e}")
            return {"success": False, "error": str(e)}

    def get_trend_components(self) -> dict[str, Any]:
        """Chronos is end-to-end, doesn't output trend/seasonality explicitly."""
        return {"note": "Decomposition not available in FMs"}


# Singleton
_predictor: CostPredictor | None = None

def get_predictor() -> CostPredictor:
    """Get predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = CostPredictor()
    return _predictor
