"""
CloudPulse AI - ML Service
API endpoint tests.
"""
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
    async def test_predict_without_training(self, client: AsyncClient):
        """Test prediction fails without training."""
        response = await client.post(
            "/api/v1/ml/predict",
            json={"days": 7},
        )
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_detect_with_training(self, client: AsyncClient, sample_cost_data):
        """Test detection endpoint trains and detects."""
        # Convert datetime to string for JSON
        cost_data = [
            {"date": d["date"].isoformat(), "amount": d["amount"]}
            for d in sample_cost_data[:40]
        ]
        
        response = await client.post(
            "/api/v1/ml/detect",
            json={"cost_data": cost_data},
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "total_records" in data
        assert "anomalies_found" in data
    
    @pytest.mark.asyncio
    async def test_train_endpoint(self, client: AsyncClient, sample_cost_data):
        """Test train endpoint."""
        cost_data = [
            {"date": d["date"].isoformat(), "amount": d["amount"]}
            for d in sample_cost_data
        ]
        
        response = await client.post(
            "/api/v1/ml/train",
            json={"cost_data": cost_data},
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "predictor_status" in data
        assert "detector_status" in data
    
    @pytest.mark.asyncio
    async def test_single_anomaly_check_without_training(self, client: AsyncClient):
        """Test single anomaly check fails without training."""
        response = await client.post(
            "/api/v1/ml/detect/single",
            json={
                "date": "2026-01-15T00:00:00",
                "amount": 500,
            },
        )
        assert response.status_code == 400
