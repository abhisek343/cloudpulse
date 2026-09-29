"""
CloudPulse AI - ML Service
Cost prediction using Chronos when available, with a deterministic local fallback.
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
    """A stateless cost forecaster.

    Chronos is a zero-shot foundation model, so no tenant data is retained in this
    process. When the optional heavy dependency or model weights are unavailable,
    the service uses a transparent moving-average/trend forecast so the safe demo
    stack still exercises the real API path.
    """

    def __init__(self) -> None:
        self.pipeline: Optional["ChronosPipeline"] = None
        try:
            torch = _get_torch()
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        except RuntimeError:
            self.device = "cpu"
        self.model_name = f"amazon/chronos-t5-{settings.chronos_model_size}"
        self.backend = "uninitialized"
        self._last_training_date: Optional[datetime] = None

    @property
    def is_fitted(self) -> bool:
        """Return whether either the primary model or safe fallback is ready."""
        return self.pipeline is not None or self.backend == "deterministic-fallback"

    @property
    def last_training_date(self) -> Optional[datetime]:
        """Get the last model initialization/validation date."""
        return self._last_training_date

    def _load_model(self) -> None:
        """Lazy-load the optional Chronos model."""
        if self.pipeline is not None:
            return

        try:
            from chronos import ChronosPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Chronos is not installed. Install the ML service with the 'inference' extra."
            ) from exc
        torch = _get_torch()

        logger.info("Loading Chronos model %s on %s", self.model_name, self.device)
        self.pipeline = ChronosPipeline.from_pretrained(
            self.model_name,
            device_map=self.device,
            torch_dtype=torch.bfloat16,
        )
        self.backend = "chronos"
        logger.info("Chronos model loaded successfully")

    @staticmethod
    def _normalize_currency(cost_data: list[dict[str, Any]]) -> str:
        currencies = {str(item.get("currency", "USD")).strip().upper() for item in cost_data}
        if len(currencies) != 1 or not next(iter(currencies)).isalpha() or len(next(iter(currencies))) != 3:
            raise ValueError("Forecast input must contain one valid currency.")
        return next(iter(currencies))

    def prepare_data(self, cost_data: list[dict[str, Any]]) -> Any:
        """Validate and prepare a daily non-negative net-cost series."""
        if not cost_data:
            raise ValueError("Data must contain at least one cost record")

        df = pd.DataFrame(cost_data)
        if "date" not in df.columns or "amount" not in df.columns:
            raise ValueError("Data must contain 'date' and 'amount' columns")

        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        if df["date"].isna().any():
            raise ValueError("Data contains an invalid date")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        if df["amount"].isna().any() or not np.isfinite(df["amount"].to_numpy()).all():
            raise ValueError("Data contains an invalid amount")
        if (df["amount"] < 0).any():
            raise ValueError("Forecast input does not accept negative amounts")

        df = df.sort_values("date").groupby("date", as_index=False)["amount"].sum()
        if df.empty:
            raise ValueError("Data must contain at least one cost record")

        # Fill missing dates with zero so the model never treats a reporting gap
        # as an implicit change in sampling frequency.
        date_range = pd.date_range(start=df["date"].min(), end=df["date"].max(), freq="D", tz="UTC")
        df = df.set_index("date").reindex(date_range).fillna(0)
        values = df["amount"].to_numpy(dtype=np.float32)

        try:
            torch = _get_torch()
        except RuntimeError:
            return values

        return torch.tensor(values, dtype=torch.float32)

    @staticmethod
    def _last_date(cost_data: list[dict[str, Any]]) -> datetime:
        dates = pd.to_datetime([item["date"] for item in cost_data], errors="coerce", utc=True)
        if dates.isna().any():
            raise ValueError("Data contains an invalid date")
        return dates.max().to_pydatetime()

    @staticmethod
    def _to_numpy(context: Any) -> np.ndarray:
        if hasattr(context, "detach"):
            return context.detach().cpu().numpy().astype(np.float32)
        if hasattr(context, "numpy"):
            return np.asarray(context.numpy(), dtype=np.float32)
        return np.asarray(context, dtype=np.float32)

    def _build_result(
        self,
        cost_data: list[dict[str, Any]],
        days: int,
        median: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        confidence: float,
    ) -> dict[str, Any]:
        currency = self._normalize_currency(cost_data)
        last_date = self._last_date(cost_data)
        future_dates = [last_date + timedelta(days=i + 1) for i in range(days)]
        result = []
        for i, date in enumerate(future_dates):
            result.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_cost": float(max(0, median[i])),
                    "lower_bound": float(max(0, lower[i])),
                    "upper_bound": float(max(0, upper[i])),
                }
            )

        total_predicted = sum(item["predicted_cost"] for item in result)
        return {
            "success": True,
            "predictions": result,
            "summary": {
                "total_predicted_cost": round(total_predicted, 2),
                "average_daily_cost": round(total_predicted / days, 2),
                "forecast_days": days,
                "confidence_level": confidence,
                "currency": currency,
                "model": self.backend,
            },
        }

    def _fallback_forecast(self, cost_data: list[dict[str, Any]], days: int) -> dict[str, Any]:
        """Produce a deterministic, explicitly labelled local forecast."""
        values = self._to_numpy(self.prepare_data(cost_data))
        window = values[-min(7, len(values)) :]
        baseline = float(window.mean()) if len(window) else 0.0
        slope = 0.0
        if len(window) >= 2:
            slope = float(np.polyfit(np.arange(len(window)), window, 1)[0])
        median = np.array([max(0.0, baseline + slope * (index + 1)) for index in range(days)])
        margin = np.maximum(median * 0.2, 0.01)
        self.backend = "deterministic-fallback"
        self._last_training_date = datetime.now(timezone.utc)
        return self._build_result(
            cost_data,
            days,
            median,
            np.maximum(0.0, median - margin),
            median + margin,
            confidence=0.6,
        )

    def train(self, cost_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Validate context and initialize Chronos or the safe local fallback."""
        if len(cost_data) < settings.min_samples_for_training:
            return {
                "success": False,
                "error": f"Insufficient context. Need at least {settings.min_samples_for_training} days.",
            }

        try:
            self._normalize_currency(cost_data)
            self.prepare_data(cost_data)
            try:
                self._load_model()
            except Exception as exc:
                # Model weights are optional in the credential-free demo image.
                # The fallback is deterministic and retains no tenant data.
                logger.warning("Chronos unavailable; using deterministic fallback (%s)", type(exc).__name__)
                self.pipeline = None
                self.backend = "deterministic-fallback"
            self._last_training_date = datetime.now(timezone.utc)
            return {
                "success": True,
                "model": self.model_name if self.backend == "chronos" else self.backend,
                "status": "Ready (Zero-Shot)" if self.backend == "chronos" else "Ready (Deterministic Fallback)",
                "trained_at": self._last_training_date.isoformat(),
            }
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.error("Model initialization failed (%s)", type(exc).__name__)
            return {"success": False, "error": "Model initialization failed."}

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
        cost_data: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Generate a forecast from request-scoped historical context."""
        del include_history
        if not cost_data:
            return {"success": False, "error": "Cost data context is required for inference."}

        days = days or settings.forecast_days
        if days < 1 or days > 365:
            return {"success": False, "error": "Forecast horizon must be between 1 and 365 days."}

        try:
            context_tensor = self.prepare_data(cost_data)
            self._normalize_currency(cost_data)
            try:
                self._load_model()
            except Exception as exc:
                logger.warning("Chronos unavailable; using deterministic fallback (%s)", type(exc).__name__)
                self.pipeline = None
                return self._fallback_forecast(cost_data, days)

            forecast = await asyncio.to_thread(
                self._predict_with_pipeline,
                context_tensor,
                days,
            )
            forecast_tensor = forecast[0]
            torch = _get_torch()
            median = self._to_numpy(torch.median(forecast_tensor, dim=0).values)
            lower = self._to_numpy(torch.quantile(forecast_tensor, 0.1, dim=0))
            upper = self._to_numpy(torch.quantile(forecast_tensor, 0.9, dim=0))
            self.backend = "chronos"
            self._last_training_date = self._last_training_date or datetime.now(timezone.utc)
            return self._build_result(
                cost_data,
                days,
                median,
                lower,
                upper,
                settings.prediction_confidence_threshold,
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.error("Chronos prediction failed (%s)", type(exc).__name__)
            return {"success": False, "error": "Prediction failed."}

    def get_trend_components(self) -> dict[str, Any]:
        """Chronos is end-to-end and does not expose decomposition components."""
        return {"note": "Decomposition not available for the configured forecast backend.", "model": self.backend}


_predictor: CostPredictor | None = None


def get_predictor() -> CostPredictor:
    """Get the process-wide stateless predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = CostPredictor()
    return _predictor
