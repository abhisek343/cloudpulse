"""
CloudPulse AI - Cost Service Tests
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
        assert data["service"] == "cost-service"
    
    @pytest.mark.asyncio
    async def test_readiness_probe(self, client: AsyncClient):
        """Test Kubernetes readiness probe."""
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True
    
    @pytest.mark.asyncio
    async def test_liveness_probe(self, client: AsyncClient):
        """Test Kubernetes liveness probe."""
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["live"] is True


class TestCloudAccountsAPI:
    """Tests for cloud accounts endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_accounts_empty(self, client: AsyncClient):
        """Test listing accounts when empty."""
        response = await client.get("/api/v1/accounts/")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1
    
    @pytest.mark.asyncio
    async def test_create_account_invalid_provider(self, client: AsyncClient):
        """Test creating account with invalid provider."""
        response = await client.post(
            "/api/v1/accounts/",
            json={
                "provider": "invalid",
                "account_id": "123456789012",
                "account_name": "Test Account",
            },
        )
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_account(self, client: AsyncClient):
        """Test getting a non-existent account."""
        response = await client.get("/api/v1/accounts/nonexistent-id")
        assert response.status_code == 404


class TestCostsAPI:
    """Tests for cost data endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_cost_summary(self, client: AsyncClient):
        """Test getting cost summary."""
        response = await client.get("/api/v1/costs/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_cost" in data
        assert "currency" in data
        assert "by_service" in data
    
    @pytest.mark.asyncio
    async def test_get_cost_trend(self, client: AsyncClient):
        """Test getting cost trend."""
        response = await client.get("/api/v1/costs/trend")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_get_costs_by_service(self, client: AsyncClient):
        """Test getting costs by service."""
        response = await client.get("/api/v1/costs/by-service")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_list_cost_records(self, client: AsyncClient):
        """Test listing cost records with pagination."""
        response = await client.get(
            "/api/v1/costs/records",
            params={"page": 1, "page_size": 10},
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 10
