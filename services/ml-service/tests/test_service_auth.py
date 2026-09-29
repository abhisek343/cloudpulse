"""Regression tests for the ML service trust boundary."""

import pytest
from httpx import AsyncClient

import app.api.auth as auth_module


@pytest.mark.asyncio
async def test_internal_ml_calls_require_token_and_organization(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch,
):
    monkeypatch.setattr(auth_module.settings, "internal_service_token", "internal-test-token")

    missing = await client.get("/api/v1/ml/status")
    assert missing.status_code == 401

    wrong = await client.get(
        "/api/v1/ml/status",
        headers={
            "X-Internal-Service-Token": "wrong-token",
            "X-Organization-ID": "org-a",
        },
    )
    assert wrong.status_code == 401

    missing_org = await client.get(
        "/api/v1/ml/status",
        headers={"X-Internal-Service-Token": "internal-test-token"},
    )
    assert missing_org.status_code == 401

    valid = await client.get(
        "/api/v1/ml/status",
        headers={
            "X-Internal-Service-Token": "internal-test-token",
            "X-Organization-ID": "org-a",
        },
    )
    assert valid.status_code == 200

    # A user JWT is accepted as a user caller, but cannot override a bad
    # service token when the internal header is present.
    mixed = await client.get(
        "/api/v1/ml/status",
        headers={
            **auth_headers,
            "X-Internal-Service-Token": "wrong-token",
            "X-Organization-ID": "org-a",
        },
    )
    assert mixed.status_code == 401
