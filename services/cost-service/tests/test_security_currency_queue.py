"""Regression coverage for secrets, denominations, and sync lifecycle."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.cloud_accounts as cloud_accounts_api
import app.core.events as events
import app.core.security as security
import app.worker as worker_module
from app.models import CloudAccount, CostRecord
from app.services.currency import normalize_currency
from app.worker import Worker


def test_live_credentials_fail_closed_without_encryption_key(monkeypatch):
    secret = "dummy-live-secret"
    monkeypatch.setattr(security.settings, "cloud_sync_mode", "live")
    monkeypatch.setattr(security.settings, "account_credentials_key", None)

    with pytest.raises(RuntimeError, match="ACCOUNT_CREDENTIALS_KEY") as exc_info:
        security.encrypt_credentials(
            {"mode": "live", "access_key_id": "dummy-access", "secret_access_key": secret}
        )
    assert secret not in str(exc_info.value)


def test_credentials_encrypt_round_trip_and_wrong_or_corrupt_key_is_safe(monkeypatch):
    secret = "dummy-secret-value"
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(security.settings, "cloud_sync_mode", "live")
    monkeypatch.setattr(security.settings, "account_credentials_key", key)

    stored = security.encrypt_credentials(
        {"mode": "live", "access_key_id": "dummy-access", "secret_access_key": secret}
    )
    assert stored is not None
    assert stored["_encrypted"] is True
    assert secret not in str(stored)
    assert security.decrypt_credentials(stored)["secret_access_key"] == secret

    monkeypatch.setattr(security.settings, "account_credentials_key", Fernet.generate_key().decode())
    with pytest.raises(RuntimeError, match="Unable to decrypt") as wrong_key:
        security.decrypt_credentials(stored)
    assert secret not in str(wrong_key.value)

    monkeypatch.setattr(security.settings, "account_credentials_key", key)
    corrupted = {**stored, "ciphertext": f"{stored['ciphertext']}corrupted"}
    with pytest.raises(RuntimeError, match="Unable to decrypt") as corrupt:
        security.decrypt_credentials(corrupted)
    assert secret not in str(corrupt.value)


def test_demo_mode_needs_no_real_credentials(monkeypatch):
    monkeypatch.setattr(security.settings, "cloud_sync_mode", "demo")
    monkeypatch.setattr(security.settings, "account_credentials_key", None)
    demo_config = {"mode": "demo", "scenario": "saas", "simulated_provider": "aws"}
    assert security.encrypt_credentials(demo_config) == demo_config
    assert security.decrypt_credentials(demo_config) == demo_config


def test_demo_mode_drops_unexpected_sensitive_fields(monkeypatch):
    monkeypatch.setattr(security.settings, "cloud_sync_mode", "demo")
    monkeypatch.setattr(security.settings, "account_credentials_key", None)
    demo_config = {
        "mode": "demo",
        "scenario": "saas",
        "secret_access_key": "dummy-demo-secret",
        "api_key": "dummy-demo-api-key",
    }

    stored = security.encrypt_credentials(demo_config)
    assert stored == {"mode": "demo", "scenario": "saas"}
    assert "dummy-demo-secret" not in str(stored)
    assert security.decrypt_credentials(demo_config) == {"mode": "demo", "scenario": "saas"}


@pytest.mark.asyncio
async def test_account_api_rejects_live_plaintext_credentials(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    secret = "dummy-api-secret"
    monkeypatch.setattr(security.settings, "cloud_sync_mode", "live")
    monkeypatch.setattr(security.settings, "account_credentials_key", None)

    response = await client.post(
        "/api/v1/accounts/",
        headers=auth_headers,
        json={
            "provider": "aws",
            "account_id": "credential-policy-account",
            "account_name": "Credential Policy Account",
            "credentials": {
                "mode": "live",
                "access_key_id": "dummy-access",
                "secret_access_key": secret,
            },
        },
    )
    assert response.status_code == 503
    assert secret not in response.text


@pytest.mark.asyncio
async def test_account_api_never_serializes_credentials(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    secret = "dummy-api-secret"
    monkeypatch.setattr(security.settings, "cloud_sync_mode", "live")
    monkeypatch.setattr(security.settings, "account_credentials_key", Fernet.generate_key().decode())

    response = await client.post(
        "/api/v1/accounts/",
        headers=auth_headers,
        json={
            "provider": "aws",
            "account_id": "credential-response-account",
            "account_name": "Credential Response Account",
            "credentials": {
                "mode": "live",
                "access_key_id": "dummy-access",
                "secret_access_key": secret,
            },
        },
    )
    assert response.status_code == 201
    assert "credentials" not in response.json()
    assert secret not in response.text


def test_currency_validation_is_explicit():
    assert normalize_currency(" eur ") == "EUR"
    assert normalize_currency(None, required=False) == "UNKNOWN"
    with pytest.raises(ValueError):
        normalize_currency(None)
    with pytest.raises(ValueError):
        normalize_currency("US")
    with pytest.raises(ValueError):
        normalize_currency("US$")


@pytest.mark.asyncio
async def test_mixed_currency_summary_and_trend_are_grouped(
    client: AsyncClient,
    seeded_cost_data: dict[str, object],
    db_session: AsyncSession,
):
    account = await db_session.get(CloudAccount, seeded_cost_data["account_id"])
    db_session.add(
        CostRecord(
            cloud_account_id=account.id,
            date=datetime.now(UTC),
            granularity="daily",
            service="Amazon EC2",
            region="eu-west-1",
            amount=Decimal("25.00"),
            currency="EUR",
        )
    )
    await db_session.commit()

    summary_response = await client.get(
        "/api/v1/costs/summary",
        headers=seeded_cost_data["headers"],
        params={"account_id": account.id, "days": 30},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total_cost"] is None
    assert summary["currency"] is None
    assert summary["currency_totals"] == {"EUR": "25.00000000", "USD": "225.00000000"}
    assert summary["by_service"] == {}
    assert summary["by_service_by_currency"]["Amazon EC2"]["EUR"] == "25.00000000"

    trend_response = await client.get(
        "/api/v1/costs/trend",
        headers=seeded_cost_data["headers"],
        params={"account_id": account.id, "days": 7},
    )
    assert trend_response.status_code == 200
    trend = trend_response.json()
    assert {point["currency"] for point in trend} == {"EUR", "USD"}
    assert all("currency" in point for point in trend)


@pytest.mark.asyncio
async def test_sync_publish_failure_is_durable_and_not_success(
    client: AsyncClient,
    seeded_cost_data: dict[str, object],
):
    secret = "dummy-broker-secret"
    with patch.object(
        cloud_accounts_api,
        "publish_sync_task",
        new=AsyncMock(side_effect=RuntimeError(f"password={secret}")),
    ):
        response = await client.post(
            f"/api/v1/accounts/{seeded_cost_data['account_id']}/sync",
            headers=seeded_cost_data["headers"],
        )

    assert response.status_code == 503
    assert secret not in response.text

    status_response = await client.get(
        f"/api/v1/accounts/{seeded_cost_data['account_id']}/status",
        headers=seeded_cost_data["headers"],
    )
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["last_sync_status"] == "failed"
    assert status["latest_task_status"] == "failed"
    assert secret not in status["latest_task_error"]


@pytest.mark.asyncio
async def test_publish_sync_task_raises_on_broker_failure(monkeypatch):
    secret = "dummy-broker-secret"

    async def fail_connect(_url):
        raise RuntimeError(f"token={secret}")

    monkeypatch.setattr(events, "connect_robust", fail_connect)
    with pytest.raises(RuntimeError, match="Failed to publish sync task") as exc_info:
        await events.publish_sync_task({"type": "sync_account", "task_id": "task-1"})
    assert secret not in str(exc_info.value)


@pytest.mark.asyncio
async def test_worker_retry_exhaustion_is_marked_failed(monkeypatch):
    worker = Worker()
    persist = AsyncMock()
    monkeypatch.setattr(worker, "_persist_task_state", persist)
    monkeypatch.setattr(worker_module.settings, "sync_max_attempts", 3)

    await worker._handle_task_failure(
        {
            "task_id": "task-1",
            "organization_id": "org-1",
            "account_id": "account-1",
            "attempt": 2,
        },
        "password=dummy-worker-secret",
    )

    persist.assert_awaited_once()
    kwargs = persist.await_args.kwargs
    assert kwargs["status"] == "failed"
    assert kwargs["completed"] is True
    assert kwargs["attempt"] == 3
    assert "dummy-worker-secret" not in kwargs["error"]


@pytest.mark.asyncio
async def test_worker_retry_publication_failure_is_not_swallowed(monkeypatch):
    worker = Worker()
    persist = AsyncMock()
    publish = AsyncMock(side_effect=RuntimeError("broker unavailable"))
    monkeypatch.setattr(worker, "_persist_task_state", persist)
    monkeypatch.setattr(worker_module, "publish_sync_task", publish)
    monkeypatch.setattr(worker_module.settings, "sync_max_attempts", 3)

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await worker._handle_task_failure(
            {
                "task_id": "task-2",
                "organization_id": "org-2",
                "account_id": "account-2",
                "attempt": 0,
            },
            "provider unavailable",
        )

    assert [call.kwargs["status"] for call in persist.await_args_list] == ["queued", "failed"]
    assert persist.await_args_list[-1].kwargs["completed"] is True
