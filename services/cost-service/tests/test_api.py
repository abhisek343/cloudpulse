"""
CloudPulse AI - Cost Service Tests
API endpoint tests.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.health as health_module
import app.services.providers.aws as aws_provider_module
from app.models import CloudAccount, CostRecord, User


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

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client: AsyncClient):
        """Metrics endpoint should expose Prometheus counters."""
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "cloudpulse_cost_service_http_requests_total" in response.text

    @pytest.mark.asyncio
    async def test_runtime_status(self, client: AsyncClient):
        """Runtime status should expose demo/live mode and provider readiness."""
        response = await client.get("/api/v1/health/runtime")
        assert response.status_code == 200

        data = response.json()
        assert data["cloud_sync_mode"] in {"demo", "live"}
        assert "allow_live_cloud_sync" in data
        assert data["default_demo_provider"] in {"aws", "azure", "gcp"}
        assert data["default_demo_scenario"] in {"saas", "startup", "enterprise", "incident"}
        assert "providers" in data
        assert set(data["providers"]) == {"aws", "azure", "gcp"}

    @pytest.mark.asyncio
    async def test_provider_preflight_reports_missing_env(self, client: AsyncClient):
        """Provider preflight should explain missing env vars when live config is incomplete."""
        response = await client.get("/api/v1/health/preflight/gcp")
        assert response.status_code == 200

        data = response.json()
        assert data["provider"] == "gcp"
        assert data["configured"] is False
        assert data["ready"] is False
        assert "GCP_BILLING_EXPORT_TABLE" in data["missing_env"]

    @pytest.mark.asyncio
    async def test_provider_preflight_runs_live_validation(self, client: AsyncClient, monkeypatch):
        """Provider preflight should run the provider smoke test when env-backed config exists."""
        monkeypatch.setattr(health_module.settings, "aws_access_key_id", "demo-key")
        monkeypatch.setattr(health_module.settings, "aws_secret_access_key", "demo-secret")
        monkeypatch.setattr(aws_provider_module.settings, "aws_access_key_id", "demo-key")
        monkeypatch.setattr(aws_provider_module.settings, "aws_secret_access_key", "demo-secret")

        async def fake_validate(self) -> dict[str, str]:
            return {"detail": "Connected to AWS Cost Explorer from the preflight endpoint."}

        with patch(
            "app.services.providers.aws.boto3.client", return_value=MagicMock()
        ), patch.object(
            aws_provider_module.AWSCostProvider,
            "validate_live_access",
            fake_validate,
        ):
            response = await client.get("/api/v1/health/preflight/aws")

        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["ready"] is True
        assert data["checks"][-1]["status"] == "passed"
        assert "preflight endpoint" in data["checks"][-1]["detail"]


class TestCloudAccountsAPI:
    """Tests for cloud accounts endpoints."""

    @pytest.mark.asyncio
    async def test_list_accounts_requires_auth(self, client: AsyncClient):
        """Test listing accounts requires authentication."""
        response = await client.get("/api/v1/accounts/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_accounts_empty(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test listing accounts when empty."""
        response = await client.get("/api/v1/accounts/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_create_account_invalid_provider(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """Test creating account with invalid provider."""
        response = await client.post(
            "/api/v1/accounts/",
            headers=auth_headers,
            json={
                "provider": "invalid",
                "account_id": "123456789012",
                "account_name": "Test Account",
            },
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_nonexistent_account(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test getting a non-existent account."""
        response = await client.get("/api/v1/accounts/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_and_list_account(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test creating an account and listing it."""
        create_response = await client.post(
            "/api/v1/accounts/",
            headers=auth_headers,
            json={
                "provider": "aws",
                "account_id": "123456789012",
                "account_name": "Production Account",
            },
        )
        assert create_response.status_code == 201

        list_response = await client.get("/api/v1/accounts/", headers=auth_headers)
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1


class TestCostsAPI:
    """Tests for cost data endpoints."""

    @pytest.mark.asyncio
    async def test_get_cost_summary(self, client: AsyncClient, seeded_cost_data: dict[str, object]):
        """Test getting cost summary."""
        response = await client.get("/api/v1/costs/summary", headers=seeded_cost_data["headers"])
        assert response.status_code == 200

        data = response.json()
        assert "total_cost" in data
        assert data["total_cost"] == "225.00000000"
        assert "currency" in data
        assert "by_service" in data

    @pytest.mark.asyncio
    async def test_get_cost_trend(self, client: AsyncClient, seeded_cost_data: dict[str, object]):
        """Test getting cost trend."""
        response = await client.get("/api/v1/costs/trend", headers=seeded_cost_data["headers"])
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_cost_trend_fills_missing_days(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ):
        """Trend output should include zero-value gaps so charts stay continuous."""
        result = await db_session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalar_one()

        account = CloudAccount(
            organization_id=user.organization_id,
            provider="aws",
            account_id="sparse-account",
            account_name="Sparse Account",
        )
        db_session.add(account)
        await db_session.flush()

        start_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        db_session.add_all(
            [
                CostRecord(
                    cloud_account_id=account.id,
                    date=start_day - timedelta(days=2),
                    granularity="daily",
                    service="Amazon EC2",
                    region="us-east-1",
                    amount=Decimal("40.00"),
                    currency="USD",
                ),
                CostRecord(
                    cloud_account_id=account.id,
                    date=start_day,
                    granularity="daily",
                    service="Amazon EC2",
                    region="us-east-1",
                    amount=Decimal("60.00"),
                    currency="USD",
                ),
            ]
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/costs/trend",
            headers=auth_headers,
            params={"days": 7, "account_id": account.id},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 7
        assert any(point["amount"] == "0" for point in data)

    @pytest.mark.asyncio
    async def test_get_costs_by_service(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
    ):
        """Test getting costs by service."""
        response = await client.get("/api/v1/costs/by-service", headers=seeded_cost_data["headers"])
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_list_cost_records(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
    ):
        """Test listing cost records with pagination."""
        response = await client.get(
            "/api/v1/costs/records",
            headers=seeded_cost_data["headers"],
            params={"page": 1, "page_size": 10},
        )
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 10


class TestAuthAPI:
    """Tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_and_login(self, client: AsyncClient):
        """Test user registration and login flow."""
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new-user@example.com",
                "password": "Password123!",
                "organization_name": "New Org",
                "full_name": "New User",
            },
        )
        assert register_response.status_code == 201

        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "new-user@example.com",
                "password": "Password123!",
            },
        )
        assert login_response.status_code == 200
        payload = login_response.json()
        assert "access_token" in payload
        assert "refresh_token" in payload
        assert "csrf_token" in payload
        assert "set-cookie" in login_response.headers

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self, client: AsyncClient):
        """Refresh endpoint should mint a new access token."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh-user@example.com",
                "password": "Password123!",
                "organization_name": "Refresh Org",
                "full_name": "Refresh User",
            },
        )

        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "refresh-user@example.com",
                "password": "Password123!",
            },
        )
        assert login_response.status_code == 200

        payload = login_response.json()
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": payload["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        assert "access_token" in refresh_response.json()

    @pytest.mark.asyncio
    async def test_refresh_cookie_requires_csrf(self, client: AsyncClient):
        """Cookie-based refresh should enforce CSRF validation."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf-user@example.com",
                "password": "Password123!",
                "organization_name": "CSRF Org",
                "full_name": "CSRF User",
            },
        )
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "csrf-user@example.com",
                "password": "Password123!",
            },
        )
        assert login_response.status_code == 200

        cookie_response = await client.post("/api/v1/auth/refresh", json={})
        assert cookie_response.status_code == 403
