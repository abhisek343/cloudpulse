"""
CloudPulse AI - ML Service
API endpoint tests.
"""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    @pytest.mark.asyncio
    async def test_root_health_check(self, client: AsyncClient):
        """Test root health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["service"] == "ml-service"
        assert "models" in data
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns service info."""
        response = await client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert data["docs"] == "/docs"


class TestMLEndpoints:
    """Tests for ML API endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_model_status(self, client: AsyncClient):
        """Test model status endpoint."""
        response = await client.get("/api/v1/ml/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "predictor_fitted" in data
        assert "detector_fitted" in data
    
    @pytest.mark.asyncio
    async def test_predict_requires_cost_history(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test prediction validation fails without historical cost data."""
        response = await client.post(
            "/api/v1/ml/predict",
            headers=auth_headers,
            json={"days": 7},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_with_context(self, client: AsyncClient, auth_headers: dict[str, str], sample_cost_data, monkeypatch):
        """Test prediction succeeds with cost history."""
        from app.api import ml as ml_api

        class FakePredictor:
            is_fitted = True
            last_training_date = datetime.now(timezone.utc)

            async def predict(self, days=None, include_history=False, cost_data=None):
                del include_history
                assert cost_data
                return {
                    "success": True,
                    "predictions": [
                        {
                            "date": "2026-03-01",
                            "predicted_cost": 123.0,
                            "lower_bound": 110.0,
                            "upper_bound": 140.0,
                        }
                    ],
                    "summary": {
                        "total_predicted_cost": 123.0,
                        "average_daily_cost": 123.0,
                        "forecast_days": days or 1,
                        "confidence_level": 0.8,
                    },
                }

        monkeypatch.setattr(ml_api, "get_predictor", lambda: FakePredictor())

        cost_data = [
            {"date": d["date"].isoformat(), "amount": d["amount"], "service": d["service"]}
            for d in sample_cost_data[:30]
        ]

        response = await client.post(
            "/api/v1/ml/predict",
            headers=auth_headers,
            json={"days": 7, "cost_data": cost_data},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    @pytest.mark.asyncio
    async def test_detect_with_training(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        sample_cost_data,
        monkeypatch,
    ):
        """Test detection endpoint trains and detects."""
        from app.api import ml as ml_api

        class FakeDetector:
            is_fitted = False
            baseline_stats = {"mean_cost": 120.0}

            def train(self, cost_data):
                self.is_fitted = True
                return {"success": True}

            def detect(self, cost_data):
                return {
                    "success": True,
                    "total_records": len(cost_data),
                    "anomalies_found": 1,
                    "anomaly_rate": round(100 / len(cost_data), 2),
                    "anomalies": [
                        {
                            "date": cost_data[-1]["date"].isoformat(),
                            "actual_cost": 200.0,
                            "expected_cost": 120.0,
                            "deviation_percent": 66.67,
                            "severity": "high",
                            "anomaly_score": -0.4,
                            "service": cost_data[-1]["service"],
                        }
                    ],
                }

        monkeypatch.setattr(ml_api, "get_detector", lambda: FakeDetector())

        # Convert datetime to string for JSON
        cost_data = [
            {"date": d["date"].isoformat(), "amount": d["amount"], "service": d["service"]}
            for d in sample_cost_data[:40]
        ]
        
        response = await client.post(
            "/api/v1/ml/detect",
            headers=auth_headers,
            json={"cost_data": cost_data},
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "total_records" in data
        assert "anomalies_found" in data
    
    @pytest.mark.asyncio
    async def test_train_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        sample_cost_data,
        monkeypatch,
    ):
        """Test train endpoint."""
        from app.api import ml as ml_api

        class FakePredictor:
            is_fitted = False
            last_training_date = datetime.now(timezone.utc)

            def train(self, cost_data):
                self.is_fitted = True
                return {"success": True, "trained_on": len(cost_data)}

        class FakeDetector:
            is_fitted = False
            baseline_stats = {}

            def train(self, cost_data):
                self.is_fitted = True
                return {"success": True, "samples_used": len(cost_data)}

        monkeypatch.setattr(ml_api, "get_predictor", lambda: FakePredictor())
        monkeypatch.setattr(ml_api, "get_detector", lambda: FakeDetector())

        cost_data = [
            {"date": d["date"].isoformat(), "amount": d["amount"], "service": d["service"]}
            for d in sample_cost_data
        ]
        
        response = await client.post(
            "/api/v1/ml/train",
            headers=auth_headers,
            json={"cost_data": cost_data},
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "predictor_status" in data
        assert "detector_status" in data
    
    @pytest.mark.asyncio
    async def test_single_anomaly_check_without_training(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test single anomaly check fails without training."""
        response = await client.post(
            "/api/v1/ml/detect/single",
            headers=auth_headers,
            json={
                "date": "2026-01-15T00:00:00",
                "amount": 500,
            },
        )
        assert response.status_code == 400
