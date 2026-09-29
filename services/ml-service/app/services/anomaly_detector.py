"""
CloudPulse AI - ML Service
Tenant-scoped anomaly detection using Isolation Forest.
"""
import hashlib
import logging
import os
import pickle
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AnomalyDetector:
    """An Isolation Forest model owned by one organization.

    The model artifact path is derived from a one-way organization hash and the
    artifact carries its owner identity. A detector is never shared between
    organizations, even though the registry is process-local for efficiency.
    """

    SENSITIVITY_MAP = {
        "low": 0.05,
        "medium": 0.10,
        "high": 0.15,
    }
    FEATURE_NAMES = [
        "amount",
        "day_of_week",
        "day_of_month",
        "is_weekend",
        "is_month_end",
        "cost_change",
        "cost_change_pct",
        "rolling_mean_7d",
        "deviation_from_mean",
    ]

    def __init__(self, organization_id: str | None = None) -> None:
        # The unscoped constructor is retained for direct library/unit use only.
        # API routes always obtain a detector through get_detector(org_id).
        self.organization_id = organization_id or "__local__"
        self.model: IsolationForest | None = None
        self.scaler: StandardScaler | None = None
        self.is_fitted = False
        self.feature_names = list(self.FEATURE_NAMES)
        self.baseline_stats: dict[str, float] = {}
        self._lock = threading.RLock()
        self._state_path = self._build_state_path(organization_id)
        self._load_state()

    @classmethod
    def _build_state_path(cls, organization_id: str | None) -> Path:
        base_path = Path(settings.model_path)
        if organization_id is None:
            return base_path / "anomaly_detector.pkl"
        digest = hashlib.sha256(organization_id.encode("utf-8")).hexdigest()
        return base_path / "organizations" / digest / "anomaly_detector.pkl"

    def _clear_state(self) -> None:
        self.model = None
        self.scaler = None
        self.is_fitted = False
        self.feature_names = list(self.FEATURE_NAMES)
        self.baseline_stats = {}

    def _load_state(self) -> None:
        """Load only an artifact that belongs to this exact organization."""
        if not self._state_path.exists():
            return

        try:
            with self._state_path.open("rb") as handle:
                payload = pickle.load(handle)
            if not isinstance(payload, dict):
                raise ValueError("model artifact is not an object")
            if payload.get("organization_id") != self.organization_id:
                raise ValueError("model artifact owner does not match the requested organization")
            model = payload.get("model")
            scaler = payload.get("scaler")
            feature_names = payload.get("feature_names")
            baseline_stats = payload.get("baseline_stats")
            if not isinstance(feature_names, list) or not isinstance(baseline_stats, dict):
                raise ValueError("model artifact metadata is malformed")
            if model is None or scaler is None:
                raise ValueError("model artifact is incomplete")
            self.model = model
            self.scaler = scaler
            self.feature_names = [str(name) for name in feature_names]
            self.baseline_stats = {
                str(key): float(value) for key, value in baseline_stats.items()
            }
            self.is_fitted = True
        except Exception as exc:
            logger.warning(
                "Failed to load anomaly detector state for organization %s: %s",
                self.organization_id,
                type(exc).__name__,
            )
            self._clear_state()

    def _persist_state(self) -> None:
        """Atomically persist the organization-owned detector artifact."""
        if self.model is None or self.scaler is None:
            return

        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._state_path.with_suffix(".tmp")
        payload = {
            "organization_id": self.organization_id,
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "baseline_stats": self.baseline_stats,
        }
        try:
            with temporary_path.open("wb") as handle:
                pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self._state_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _validate_input(cost_data: list[dict[str, Any]]) -> None:
        if not cost_data:
            raise ValueError("Data must contain at least one cost record")

    def prepare_features(self, cost_data: list[dict[str, Any]]) -> pd.DataFrame:
        """Prepare validated, daily cost features for anomaly detection."""
        self._validate_input(cost_data)
        df = pd.DataFrame(cost_data)
        if "date" not in df.columns or "amount" not in df.columns:
            raise ValueError("Data must contain 'date' and 'amount' columns")

        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        if df["date"].isna().any():
            raise ValueError("Data contains an invalid date")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        if df["amount"].isna().any() or not np.isfinite(df["amount"]).all():
            raise ValueError("Data contains an invalid amount")
        if (df["amount"] < 0).any():
            raise ValueError("Anomaly detection does not accept negative amounts")

        df = df.sort_values("date").reset_index(drop=True)
        if df["date"].duplicated().any():
            aggregation: dict[str, Any] = {"amount": ("amount", "sum")}
            if "service" in df.columns:
                aggregation["service"] = ("service", "first")
            df = df.groupby("date", as_index=False).agg(**aggregation)

        df["day_of_week"] = df["date"].dt.dayofweek
        df["day_of_month"] = df["date"].dt.day
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        df["is_month_end"] = df["date"].dt.is_month_end.astype(int)
        df["cost_change"] = df["amount"].diff().fillna(0)
        df["cost_change_pct"] = (
            df["amount"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0)
        )
        df["rolling_mean_7d"] = df["amount"].rolling(window=7, min_periods=1).mean()
        df["rolling_std_7d"] = df["amount"].rolling(window=7, min_periods=1).std().fillna(0)
        df["rolling_mean_30d"] = df["amount"].rolling(window=30, min_periods=1).mean()
        df["deviation_from_mean"] = (
            df["amount"] - df["rolling_mean_7d"]
        ) / (df["rolling_std_7d"] + 0.01)
        return df

    def train(self, cost_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Train and persist this organization's detector."""
        with self._lock:
            if len(cost_data) < settings.min_samples_for_training:
                return {
                    "success": False,
                    "error": f"Insufficient data. Need at least {settings.min_samples_for_training} samples.",
                }

            try:
                df = self.prepare_features(cost_data)
                if len(df) < settings.min_samples_for_training:
                    return {
                        "success": False,
                        "error": f"Insufficient unique dates. Need at least {settings.min_samples_for_training} samples.",
                    }
                X = df[self.FEATURE_NAMES].values
                scaler = StandardScaler()
                model = IsolationForest(
                    n_estimators=100,
                    contamination=self.SENSITIVITY_MAP.get(settings.anomaly_sensitivity, 0.10),
                    random_state=42,
                    n_jobs=-1,
                )
                model.fit(scaler.fit_transform(X))

                self.scaler = scaler
                self.model = model
                self.feature_names = list(self.FEATURE_NAMES)
                self.is_fitted = True
                self.baseline_stats = {
                    "mean_cost": float(df["amount"].mean()),
                    "std_cost": float(df["amount"].std() or 0),
                    "median_cost": float(df["amount"].median()),
                    "p95_cost": float(df["amount"].quantile(0.95)),
                }
                self._persist_state()
                logger.info(
                    "Anomaly detector trained for organization %s on %d samples",
                    self.organization_id,
                    len(df),
                )
                contamination = self.SENSITIVITY_MAP.get(settings.anomaly_sensitivity, 0.10)
                return {
                    "success": True,
                    "samples_used": len(df),
                    "sensitivity": settings.anomaly_sensitivity,
                    "contamination": contamination,
                    "baseline_stats": self.baseline_stats,
                }
            except Exception as exc:
                logger.error(
                    "Anomaly detector training failed for organization %s: %s",
                    self.organization_id,
                    type(exc).__name__,
                )
                return {"success": False, "error": "Anomaly detector training failed."}

    def detect(self, cost_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Detect anomalies using this organization's fitted model."""
        with self._lock:
            if not self.is_fitted or self.model is None or self.scaler is None:
                return {"success": False, "error": "Model not trained. Call train() first."}
            try:
                df = self.prepare_features(cost_data)
                currencies = {
                    str(item.get("currency", "USD")).strip().upper()
                    for item in cost_data
                }
                if len(currencies) != 1:
                    raise ValueError("Anomaly input must contain one currency")
                currency = next(iter(currencies))
                X_scaled = self.scaler.transform(df[self.feature_names].values)
                predictions = self.model.predict(X_scaled)
                scores = self.model.decision_function(X_scaled)
                anomalies = []
                for i, (pred, score) in enumerate(zip(predictions, scores)):
                    if pred != -1:
                        continue
                    row = df.iloc[i]
                    deviation = abs(row["deviation_from_mean"])
                    if deviation > 3:
                        severity = "critical"
                    elif deviation > 2:
                        severity = "high"
                    elif deviation > 1:
                        severity = "medium"
                    else:
                        severity = "low"
                    expected = row["rolling_mean_7d"]
                    actual = row["amount"]
                    deviation_pct = ((actual - expected) / expected * 100) if expected > 0 else 0
                    anomalies.append(
                        {
                            "date": row["date"].isoformat(),
                            "actual_cost": float(actual),
                            "expected_cost": float(expected),
                            "deviation_percent": round(float(deviation_pct), 2),
                            "severity": severity,
                            "anomaly_score": round(float(score), 4),
                            "service": row.get("service", "Unknown"),
                            "currency": currency,
                        }
                    )
                return {
                    "success": True,
                    "total_records": len(df),
                    "anomalies_found": len(anomalies),
                    "anomaly_rate": round(len(anomalies) / len(df) * 100, 2),
                    "anomalies": sorted(anomalies, key=lambda item: item["date"], reverse=True),
                }
            except Exception as exc:
                logger.error(
                    "Anomaly detection failed for organization %s: %s",
                    self.organization_id,
                    type(exc).__name__,
                )
                return {"success": False, "error": "Anomaly detection failed."}

    def detect_single(self, record: dict[str, Any]) -> dict[str, Any]:
        """Check one non-negative cost record against this organization's baseline."""
        with self._lock:
            if not self.is_fitted:
                return {"is_anomaly": False, "error": "Model not trained"}
            try:
                amount = float(record.get("amount", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError("Amount must be numeric") from exc
            if not np.isfinite(amount) or amount < 0:
                raise ValueError("Amount must be a finite non-negative number")
            mean = self.baseline_stats.get("mean_cost", 0)
            std = self.baseline_stats.get("std_cost", 0)
            z_score = (amount - mean) / std if std > 0 else 0
            is_anomaly = abs(z_score) > 2.5
            severity = "low"
            if abs(z_score) > 4:
                severity = "critical"
            elif abs(z_score) > 3:
                severity = "high"
            elif abs(z_score) > 2:
                severity = "medium"
            return {
                "is_anomaly": is_anomaly,
                "severity": severity if is_anomaly else None,
                "z_score": round(z_score, 2),
                "amount": amount,
                "baseline_mean": round(mean, 2),
                "baseline_std": round(std, 2),
            }


_detector_registry: dict[str, AnomalyDetector] = {}
_registry_lock = threading.RLock()


def get_detector(organization_id: str | None = None) -> AnomalyDetector:
    """Return the detector for one organization, never a shared tenant model."""
    registry_key = organization_id or "__local__"
    with _registry_lock:
        detector = _detector_registry.get(registry_key)
        if detector is None:
            detector = AnomalyDetector(organization_id)
            _detector_registry[registry_key] = detector
        return detector


def clear_detector_registry() -> None:
    """Clear in-process detectors for tests and controlled worker reloads."""
    with _registry_lock:
        _detector_registry.clear()
