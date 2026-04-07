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
from app.core.config import get_settings
from app.main import app
from app.models import CloudAccount, CostRecord, User
from app.services.llm_service import get_llm_service


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
        assert data["cost_data_retention_months"] >= 1
        assert data["default_demo_provider"] in {"aws", "azure", "gcp"}
        assert data["default_demo_scenario"] in {"saas", "startup", "enterprise", "incident"}
        assert "llm_enabled" in data
        assert "llm_ready" in data
        assert data["llm_execution_mode"] in {"external", "local"}
        assert "llm_allow_external_inference" in data
        assert data["llm_context_policy"] == "summary_only"
        assert "llm_notice" in data
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
                "business_unit": "platform",
                "environment": "production",
                "cost_center": "cc-001",
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["business_unit"] == "platform"
        assert created["environment"] == "production"
        assert created["cost_center"] == "cc-001"
        assert created["last_sync_status"] == "never_synced"

        list_response = await client.get("/api/v1/accounts/", headers=auth_headers)
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_detect_demo_account(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Demo detection should prefill a ready-to-use demo account."""
        response = await client.post(
            "/api/v1/accounts/detect",
            headers=auth_headers,
            json={
                "provider": "demo",
                "credentials": {"scenario": "incident", "simulated_provider": "gcp"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == "demo-incident-001"
        assert data["account_name"] == "Demo INCIDENT Workspace"
        assert data["detected_metadata"]["simulated_provider"] == "gcp"

    @pytest.mark.asyncio
    async def test_detect_aws_account(self, client: AsyncClient, auth_headers: dict[str, str]):
        """AWS detection should use STS to infer the current account ID."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/tester",
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts

        with patch("app.api.cloud_accounts.boto3.Session", return_value=mock_session):
            response = await client.post(
                "/api/v1/accounts/detect",
                headers=auth_headers,
                json={"provider": "aws", "credentials": {}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == "123456789012"
        assert data["confidence"] == "high"
        assert data["detected_metadata"]["caller_arn"].endswith(":user/tester")

    @pytest.mark.asyncio
    async def test_account_status_reports_data_coverage(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
    ):
        """Account status should summarize imported records and coverage dates."""
        account_id = str(seeded_cost_data["account_id"])

        response = await client.get(
            f"/api/v1/accounts/{account_id}/status",
            headers=seeded_cost_data["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == account_id
        assert data["total_records"] == 3
        assert data["services_detected"] == 2
        assert data["coverage_start"] is not None
        assert data["coverage_end"] is not None


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
    async def test_cost_summary_filters_by_business_unit(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
        db_session: AsyncSession,
    ) -> None:
        """Grouping filters should scope aggregations at the cloud-account level."""
        result = await db_session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalar_one()

        seeded_account = await db_session.get(CloudAccount, seeded_cost_data["account_id"])
        seeded_account.business_unit = "platform"

        extra_account = CloudAccount(
            organization_id=user.organization_id,
            provider="aws",
            account_id="secondary-account",
            account_name="Secondary Account",
            business_unit="finance",
        )
        db_session.add(extra_account)
        await db_session.flush()
        db_session.add(
            CostRecord(
                cloud_account_id=extra_account.id,
                date=datetime.now(UTC),
                granularity="daily",
                service="Amazon Athena",
                region="us-east-1",
                amount=Decimal("999.00"),
                currency="USD",
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/costs/summary",
            headers=seeded_cost_data["headers"],
            params={"business_unit": "platform"},
        )
        assert response.status_code == 200
        assert response.json()["total_cost"] == "225.00000000"

    @pytest.mark.asyncio
    async def test_cost_reconciliation_returns_match(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
    ) -> None:
        """Reconciliation should compare imported totals to a fresh provider total."""

        class FakeProvider:
            mode = "demo"

            async def get_cost_data(self, start_date, end_date, granularity="DAILY"):
                del start_date, end_date, granularity
                return [
                    {"amount": Decimal("100.00")},
                    {"amount": Decimal("50.00")},
                    {"amount": Decimal("75.00")},
                ]

        with patch("app.api.costs.ProviderFactory.get_provider", return_value=FakeProvider()):
            response = await client.get(
                "/api/v1/costs/reconciliation",
                headers=seeded_cost_data["headers"],
                params={"account_id": seeded_cost_data["account_id"], "days": 30},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "matched"
        assert data["imported_total"] == "225.00"
        assert data["provider_total"] == "225.00"

    @pytest.mark.asyncio
    async def test_cost_export_returns_csv(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
    ) -> None:
        """CSV export should return a downloadable attachment with filtered rows."""
        response = await client.get("/api/v1/costs/export", headers=seeded_cost_data["headers"])
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment;" in response.headers["content-disposition"]
        body = response.text
        assert "account_name" in body
        assert "Test AWS Account" in body


class TestChatAPI:
    """Tests for chat analysis endpoints."""

    @pytest.mark.asyncio
    async def test_chat_respects_external_inference_policy(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Hosted inference should be blocked when runtime policy disables it."""
        base_settings = get_settings()

        class PolicySettings:
            def __init__(self, source) -> None:
                self._source = source
                self.llm_enabled = True
                self.llm_api_key = "test-key"
                self.llm_allow_external_inference = False
                self.llm_provider = source.llm_provider
                self.llm_model = source.llm_model

            def __getattr__(self, item: str):
                return getattr(self._source, item)

        class FakeLLMService:
            def is_external_provider(self) -> bool:
                return True

            def requires_api_key(self) -> bool:
                return True

        app.dependency_overrides[get_settings] = lambda: PolicySettings(base_settings)
        app.dependency_overrides[get_llm_service] = lambda: FakeLLMService()
        try:
            response = await client.post(
                "/api/v1/chat/analyze",
                headers=auth_headers,
                json={"message": "hello"},
            )
        finally:
            app.dependency_overrides.pop(get_settings, None)
            app.dependency_overrides.pop(get_llm_service, None)

        assert response.status_code == 503
        assert "external inference is disabled" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_chat_masks_account_scope_in_prompt_context(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
    ) -> None:
        """Prompt context should avoid leaking raw account identifiers upstream."""
        captured: dict[str, object] = {}

        class FakeLLMService:
            def is_external_provider(self) -> bool:
                return True

            def requires_api_key(self) -> bool:
                return True

            async def get_chat_response(self, message: str, context_data: dict | None = None) -> str:
                captured["message"] = message
                captured["context"] = context_data or {}
                return "ok"

        app.dependency_overrides[get_llm_service] = lambda: FakeLLMService()
        try:
            response = await client.post(
                "/api/v1/chat/analyze",
                headers=seeded_cost_data["headers"],
                json={
                    "message": "What changed?",
                    "context_keys": {"account_id": seeded_cost_data["account_id"]},
                },
            )
        finally:
            app.dependency_overrides.pop(get_llm_service, None)

        assert response.status_code == 200
        context = captured["context"]
        assert "account_id" not in context
        assert context["account_scope"].startswith(str(seeded_cost_data["account_id"])[:2])
        assert context["account_scope"].endswith(str(seeded_cost_data["account_id"])[-4:])
        assert context["context_policy"] == "summary_only"

    @pytest.mark.asyncio
    async def test_chat_returns_grounding_metadata(
        self,
        client: AsyncClient,
        seeded_cost_data: dict[str, object],
        db_session: AsyncSession,
    ) -> None:
        """Chat responses should report the exact analysis scope used."""
        account = await db_session.get(CloudAccount, seeded_cost_data["account_id"])
        account.business_unit = "platform"
        account.environment = "production"
        account.cost_center = "cc-007"
        await db_session.commit()

        class FakeLLMService:
            def is_external_provider(self) -> bool:
                return True

            def requires_api_key(self) -> bool:
                return True

            async def get_chat_response(self, message: str, context_data: dict | None = None) -> str:
                del message, context_data
                return "grounded"

        app.dependency_overrides[get_llm_service] = lambda: FakeLLMService()
        try:
            response = await client.post(
                "/api/v1/chat/analyze",
                headers=seeded_cost_data["headers"],
                json={
                    "message": "Summarize platform production spend",
                    "time_range": "last_30_days",
                    "context_keys": {
                        "account_id": seeded_cost_data["account_id"],
                        "business_unit": "platform",
                        "environment": "production",
                        "cost_center": "cc-007",
                    },
                },
            )
        finally:
            app.dependency_overrides.pop(get_llm_service, None)

        assert response.status_code == 200
        grounding = response.json()["grounding"]
        assert grounding["account_id"] == seeded_cost_data["account_id"]
        assert grounding["account_name"] == "Test AWS Account"
        assert grounding["business_unit"] == "platform"
        assert grounding["environment"] == "production"
        assert grounding["cost_center"] == "cc-007"

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
    async def test_refresh_rotation_invalidates_prior_refresh_token(self, client: AsyncClient):
        """Refresh tokens should be single-use after rotation."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "rotating-user@example.com",
                "password": "Password123!",
                "organization_name": "Rotation Org",
                "full_name": "Rotation User",
            },
        )

        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "rotating-user@example.com",
                "password": "Password123!",
            },
        )
        assert login_response.status_code == 200

        original_refresh_token = login_response.json()["refresh_token"]
        first_refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh_token},
        )
        assert first_refresh_response.status_code == 200

        replay_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh_token},
        )
        assert replay_response.status_code == 401
        assert "revoked" in replay_response.json()["detail"].lower()

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

    @pytest.mark.asyncio
    async def test_logout_revokes_access_and_refresh_tokens(self, client: AsyncClient):
        """Logout should invalidate the current access and refresh tokens."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout-user@example.com",
                "password": "Password123!",
                "organization_name": "Logout Org",
                "full_name": "Logout User",
            },
        )

        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "logout-user@example.com",
                "password": "Password123!",
            },
        )
        assert login_response.status_code == 200
        payload = login_response.json()

        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
            json={
                "access_token": payload["access_token"],
                "refresh_token": payload["refresh_token"],
            },
        )
        assert logout_response.status_code == 204

        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        assert me_response.status_code == 401

        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": payload["refresh_token"]},
        )
        assert refresh_response.status_code == 401
        assert "revoked" in refresh_response.json()["detail"].lower()
