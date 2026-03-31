"""
CloudPulse AI - ML Service
Anomaly detection using Isolation Forest.
"""
import logging
import pickle
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
    """
    Cost anomaly detection using Isolation Forest.
    
    Isolation Forest is effective for anomaly detection because:
    - Works well with high-dimensional data
    - Doesn't require labeled data (unsupervised)
    - Fast training and prediction
    - Handles outliers naturally
    """
    
    SENSITIVITY_MAP = {
        "low": 0.05,      # 5% contamination - fewer anomalies detected
        "medium": 0.10,   # 10% contamination
        "high": 0.15,     # 15% contamination - more anomalies detected
    }
    
    def __init__(self) -> None:
        self.model: IsolationForest | None = None
        self.scaler: StandardScaler | None = None
        self.is_fitted: bool = False
        self.feature_names: list[str] = []
        self.baseline_stats: dict[str, float] = {}
        self._state_path = Path(settings.model_path) / "anomaly_detector.pkl"
        self._load_state()

    def _load_state(self) -> None:
        """Load persisted anomaly-detector state when available."""
        if not self._state_path.exists():
            return

        try:
            with self._state_path.open("rb") as handle:
                payload = pickle.load(handle)
            self.model = payload.get("model")
            self.scaler = payload.get("scaler")
            self.feature_names = payload.get("feature_names", [])
            self.baseline_stats = payload.get("baseline_stats", {})
            self.is_fitted = self.model is not None and self.scaler is not None
        except Exception as exc:
            logger.warning("Failed to load anomaly detector state: %s", exc)
            self.model = None
            self.scaler = None
            self.is_fitted = False
            self.feature_names = []
            self.baseline_stats = {}

    def _persist_state(self) -> None:
        """Persist the trained anomaly-detector state to disk."""
        if self.model is None or self.scaler is None:
            return

        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._state_path.open("wb") as handle:
            pickle.dump(
                {
                    "model": self.model,
                    "scaler": self.scaler,
                    "feature_names": self.feature_names,
                    "baseline_stats": self.baseline_stats,
                },
                handle,
            )
    
    def prepare_features(self, cost_data: list[dict[str, Any]]) -> pd.DataFrame:
        """
        Prepare features for anomaly detection.
        
        Features:
        - Daily cost amount
        - Day of week (cyclical)
        - Day of month
        - Cost change from previous day
        - Rolling averages
        """
        df = pd.DataFrame(cost_data)
        
        # Ensure date column
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        else:
            raise ValueError("Data must contain 'date' column")
        
        # Ensure amount column
        if "amount" not in df.columns:
            raise ValueError("Data must contain 'amount' column")
        
        df = df.sort_values("date").reset_index(drop=True)
        df["amount"] = df["amount"].astype(float)
        
        # Time-based features
        df["day_of_week"] = df["date"].dt.dayofweek
        df["day_of_month"] = df["date"].dt.day
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        df["is_month_end"] = (df["date"].dt.is_month_end).astype(int)
        
        # Cost change features
        df["cost_change"] = df["amount"].diff().fillna(0)
        df["cost_change_pct"] = df["amount"].pct_change().fillna(0).replace([np.inf, -np.inf], 0)
        
        # Rolling statistics
        df["rolling_mean_7d"] = df["amount"].rolling(window=7, min_periods=1).mean()
        df["rolling_std_7d"] = df["amount"].rolling(window=7, min_periods=1).std().fillna(0)
        df["rolling_mean_30d"] = df["amount"].rolling(window=30, min_periods=1).mean()
        
        # Deviation from rolling mean
        df["deviation_from_mean"] = (df["amount"] - df["rolling_mean_7d"]) / (df["rolling_std_7d"] + 0.01)
        
        self.feature_names = [
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
        
        return df
    
    def train(self, cost_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Train the Isolation Forest model.
        
        Args:
            cost_data: List of dicts with 'date' and 'amount' keys
            
        Returns:
            Training status and metrics
        """
        if len(cost_data) < settings.min_samples_for_training:
            return {
                "success": False,
                "error": f"Insufficient data. Need at least {settings.min_samples_for_training} samples.",
            }
        
        try:
            df = self.prepare_features(cost_data)
            X = df[self.feature_names].values
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Get contamination based on sensitivity
            contamination = self.SENSITIVITY_MAP.get(
                settings.anomaly_sensitivity,
                0.10,
            )
            
            # Train Isolation Forest
            self.model = IsolationForest(
                n_estimators=100,
                contamination=contamination,
                random_state=42,
                n_jobs=-1,
            )
            self.model.fit(X_scaled)
            self.is_fitted = True
            
            # Calculate baseline statistics
            self.baseline_stats = {
                "mean_cost": float(df["amount"].mean()),
                "std_cost": float(df["amount"].std()),
                "median_cost": float(df["amount"].median()),
                "p95_cost": float(df["amount"].quantile(0.95)),
            }
            self._persist_state()
            
            logger.info(f"Anomaly detector trained on {len(df)} samples")
            
            return {
                "success": True,
                "samples_used": len(df),
                "sensitivity": settings.anomaly_sensitivity,
                "contamination": contamination,
                "baseline_stats": self.baseline_stats,
            }
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def detect(self, cost_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Detect anomalies in cost data.
        
        Args:
            cost_data: List of dicts with 'date' and 'amount' keys
            
        Returns:
            Anomaly detection results
        """
        if not self.is_fitted:
            return {
                "success": False,
                "error": "Model not trained. Call train() first.",
            }
        
        try:
            df = self.prepare_features(cost_data)
            X = df[self.feature_names].values
            X_scaled = self.scaler.transform(X)
            
            # Predict anomalies (-1 = anomaly, 1 = normal)
            predictions = self.model.predict(X_scaled)
            scores = self.model.decision_function(X_scaled)
            
            # Build results
            anomalies = []
            for i, (pred, score) in enumerate(zip(predictions, scores)):
                if pred == -1:  # Anomaly detected
                    row = df.iloc[i]
                    
                    # Determine severity based on deviation
                    deviation = abs(row["deviation_from_mean"])
                    if deviation > 3:
                        severity = "critical"
                    elif deviation > 2:
                        severity = "high"
                    elif deviation > 1:
                        severity = "medium"
                    else:
                        severity = "low"
                    
                    # Calculate expected vs actual
                    expected = row["rolling_mean_7d"]
                    actual = row["amount"]
                    deviation_pct = ((actual - expected) / expected * 100) if expected > 0 else 0
                    
                    anomalies.append({
                        "date": row["date"].isoformat(),
                        "actual_cost": float(actual),
                        "expected_cost": float(expected),
                        "deviation_percent": round(float(deviation_pct), 2),
                        "severity": severity,
                        "anomaly_score": round(float(score), 4),
                        "service": row.get("service", "Unknown"),
                    })
            
            return {
                "success": True,
                "total_records": len(df),
                "anomalies_found": len(anomalies),
                "anomaly_rate": round(len(anomalies) / len(df) * 100, 2),
                "anomalies": sorted(anomalies, key=lambda x: x["date"], reverse=True),
            }
            
        except Exception as e:
            logger.error(f"Detection failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def detect_single(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Check if a single record is anomalous.
        
        Args:
            record: Dict with 'date', 'amount', and optionally 'service'
            
        Returns:
            Anomaly detection result for single record
        """
        if not self.is_fitted:
            return {
                "is_anomaly": False,
                "error": "Model not trained",
            }
        
        # Use baseline stats for quick check
        amount = float(record.get("amount", 0))
        mean = self.baseline_stats.get("mean_cost", 0)
        std = self.baseline_stats.get("std_cost", 1)
        
        z_score = (amount - mean) / std if std > 0 else 0
        
        # Quick heuristic check
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


# Singleton instance
_detector: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    """Get or create the detector instance."""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector
