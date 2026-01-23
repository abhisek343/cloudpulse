"""
CloudPulse AI - ML Service
Cost prediction using Prophet time series forecasting.
"""
import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from prophet import Prophet

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CostPredictor:
    """
    Cost prediction service using Facebook Prophet.
    
    Prophet is ideal for cost forecasting because:
    - Handles seasonality (weekly, monthly patterns)
    - Robust to missing data
    - Handles outliers well
    - Provides uncertainty intervals
    """
    
    def __init__(self) -> None:
        self.model: Prophet | None = None
        self.is_fitted: bool = False
        self.last_training_date: datetime | None = None
    
    def prepare_data(self, cost_data: list[dict[str, Any]]) -> pd.DataFrame:
        """
        Prepare cost data for Prophet.
        
        Prophet requires columns named 'ds' (datestamp) and 'y' (value).
        """
        df = pd.DataFrame(cost_data)
        
        # Ensure date column is datetime
        if "date" in df.columns:
            df["ds"] = pd.to_datetime(df["date"])
        elif "ds" not in df.columns:
            raise ValueError("Data must contain 'date' or 'ds' column")
        
        # Ensure we have the target column
        if "amount" in df.columns:
            df["y"] = df["amount"].astype(float)
        elif "y" not in df.columns:
            raise ValueError("Data must contain 'amount' or 'y' column")
        
        # Sort by date
        df = df.sort_values("ds").reset_index(drop=True)
        
        # Fill missing dates with 0
        date_range = pd.date_range(start=df["ds"].min(), end=df["ds"].max(), freq="D")
        df = df.set_index("ds").reindex(date_range).fillna(0).reset_index()
        df.columns = ["ds", "y"] + list(df.columns[2:])
        
        return df[["ds", "y"]]
    
    def train(self, cost_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Train the Prophet model on historical cost data.
        
        Args:
            cost_data: List of dicts with 'date' and 'amount' keys
            
        Returns:
            Training metrics and status
        """
        if len(cost_data) < settings.min_samples_for_training:
            return {
                "success": False,
                "error": f"Insufficient data. Need at least {settings.min_samples_for_training} samples.",
                "samples_provided": len(cost_data),
            }
        
        try:
            df = self.prepare_data(cost_data)
            
            # Initialize Prophet with sensible defaults for cost data
            self.model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                seasonality_mode="multiplicative",
                changepoint_prior_scale=0.05,  # Conservative to avoid overfitting
                interval_width=0.95,  # 95% confidence interval
            )
            
            # Add monthly seasonality
            self.model.add_seasonality(
                name="monthly",
                period=30.5,
                fourier_order=5,
            )
            
            # Fit the model
            self.model.fit(df)
            self.is_fitted = True
            self.last_training_date = datetime.utcnow()
            
            logger.info(f"Model trained successfully on {len(df)} samples")
            
            return {
                "success": True,
                "samples_used": len(df),
                "date_range": {
                    "start": df["ds"].min().isoformat(),
                    "end": df["ds"].max().isoformat(),
                },
                "trained_at": self.last_training_date.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def predict(
        self,
        days: int | None = None,
        include_history: bool = False,
    ) -> dict[str, Any]:
        """
        Generate cost predictions for the next N days.
        
        Args:
            days: Number of days to forecast (default: from settings)
            include_history: Whether to include historical fitted values
            
        Returns:
            Prediction results with confidence intervals
        """
        if not self.is_fitted or self.model is None:
            return {
                "success": False,
                "error": "Model not trained. Call train() first.",
            }
        
        days = days or settings.forecast_days
        
        try:
            # Create future dataframe
            future = self.model.make_future_dataframe(periods=days)
            
            # Make predictions
            forecast = self.model.predict(future)
            
            # Extract predictions
            if include_history:
                predictions = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
            else:
                predictions = forecast.tail(days)[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
            
            # Convert to list of dicts
            result = []
            for _, row in predictions.iterrows():
                result.append({
                    "date": row["ds"].isoformat(),
                    "predicted_cost": max(0, float(row["yhat"])),  # Cost can't be negative
                    "lower_bound": max(0, float(row["yhat_lower"])),
                    "upper_bound": max(0, float(row["yhat_upper"])),
                })
            
            # Calculate summary statistics
            total_predicted = sum(r["predicted_cost"] for r in result)
            avg_daily = total_predicted / len(result) if result else 0
            
            return {
                "success": True,
                "predictions": result,
                "summary": {
                    "total_predicted_cost": round(total_predicted, 2),
                    "average_daily_cost": round(avg_daily, 2),
                    "forecast_days": len(result),
                    "confidence_level": 0.95,
                },
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def get_trend_components(self) -> dict[str, Any]:
        """Get the trend and seasonality components."""
        if not self.is_fitted or self.model is None:
            return {"error": "Model not trained"}
        
        # Get the last fitted values
        future = self.model.make_future_dataframe(periods=0)
        forecast = self.model.predict(future)
        
        return {
            "trend": forecast["trend"].tolist(),
            "weekly": forecast["weekly"].tolist() if "weekly" in forecast else [],
            "yearly": forecast["yearly"].tolist() if "yearly" in forecast else [],
            "monthly": forecast["monthly"].tolist() if "monthly" in forecast else [],
        }


# Singleton instance
_predictor: CostPredictor | None = None


def get_predictor() -> CostPredictor:
    """Get or create the predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = CostPredictor()
    return _predictor
