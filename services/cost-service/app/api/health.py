"""
CloudPulse AI - Cost Service
Health check endpoints.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache, get_cache
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas import (
    HealthCheck,
    ProviderPreflightCheck,
    ProviderPreflightResult,
    RuntimeProviderStatus,
    RuntimeStatus,
)
from app.services.providers.aws import AWSCostProvider
from app.services.providers.azure import AzureProvider
from app.services.providers.gcp import GCPProvider

router = APIRouter()
settings = get_settings()

LIVE_PROVIDER_CLASSES = {
    "aws": AWSCostProvider,
    "azure": AzureProvider,
    "gcp": GCPProvider,
}


def _provider_preflight_metadata() -> dict[str, dict[str, str]]:
    """Describe env requirements and cost sources for live providers."""
    return {
        "aws": {
            "credential_source": "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
            "cost_source": "AWS Cost Explorer",
        },
        "azure": {
            "credential_source": (
                "AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET"
            ),
            "cost_source": "Azure Cost Management Query API",
        },
        "gcp": {
            "credential_source": (
                "GCP_SERVICE_ACCOUNT_JSON or GCP_SERVICE_ACCOUNT_FILE plus GCP_BILLING_EXPORT_TABLE"
            ),
            "cost_source": "BigQuery billing export",
        },
    }


def _provider_missing_env(provider: str) -> list[str]:
    """List the env vars still needed for a live provider preflight."""
    if provider == "aws":
        missing = []
        if not settings.aws_access_key_id:
            missing.append("AWS_ACCESS_KEY_ID")
        if not settings.aws_secret_access_key:
            missing.append("AWS_SECRET_ACCESS_KEY")
        return missing

    if provider == "azure":
        missing = []
        if not settings.azure_subscription_id:
            missing.append("AZURE_SUBSCRIPTION_ID")
        if not settings.azure_tenant_id:
            missing.append("AZURE_TENANT_ID")
        if not settings.azure_client_id:
            missing.append("AZURE_CLIENT_ID")
        if not settings.azure_client_secret:
            missing.append("AZURE_CLIENT_SECRET")
        return missing

    if provider == "gcp":
        missing = []
        service_account_configured = bool(
            settings.gcp_service_account_json
            or (
                settings.gcp_service_account_file
                and Path(settings.gcp_service_account_file).exists()
            )
        )
        if not service_account_configured:
            missing.append("GCP_SERVICE_ACCOUNT_JSON or GCP_SERVICE_ACCOUNT_FILE")
        if not settings.gcp_billing_export_table:
            missing.append("GCP_BILLING_EXPORT_TABLE")
        return missing

    raise HTTPException(status_code=404, detail=f"Unsupported provider: {provider}")


def _build_provider_statuses() -> dict[str, RuntimeProviderStatus]:
    """Summarize provider readiness from env-backed runtime settings."""
    aws_ready = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
    azure_ready = bool(
        settings.azure_subscription_id
        and settings.azure_tenant_id
        and settings.azure_client_id
        and settings.azure_client_secret
    )
    gcp_ready = bool(
        (
            settings.gcp_service_account_json
            or (
                settings.gcp_service_account_file
                and Path(settings.gcp_service_account_file).exists()
            )
        )
        and settings.gcp_billing_export_table
    )

    return {
        "aws": RuntimeProviderStatus(
            configured=aws_ready,
            readiness="ready" if aws_ready else "missing_credentials",
            note=(
                "Uses env-backed AWS credentials or account-level overrides."
                if aws_ready
                else "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for live sync."
            ),
        ),
        "azure": RuntimeProviderStatus(
            configured=azure_ready,
            readiness="ready" if azure_ready else "missing_credentials",
            note=(
                "Env-driven Azure adapter is configured."
                if azure_ready
                else "Set AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, AZURE_CLIENT_ID, and "
                "AZURE_CLIENT_SECRET for live sync."
            ),
        ),
        "gcp": RuntimeProviderStatus(
            configured=gcp_ready,
            readiness="ready" if gcp_ready else "missing_credentials",
            note=(
                "Uses a BigQuery billing export for live incurred-cost queries."
                if gcp_ready
                else "Set GCP_SERVICE_ACCOUNT_JSON or GCP_SERVICE_ACCOUNT_FILE and "
                "GCP_BILLING_EXPORT_TABLE for live sync."
            ),
        ),
    }


@router.get("/", response_model=HealthCheck)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[RedisCache, Depends(get_cache)],
) -> HealthCheck:
    """Comprehensive health check for all dependencies."""
    # Check database
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    # Check Redis
    redis_status = "connected"
    try:
        await cache.client.ping()
    except Exception:
        redis_status = "disconnected"

    return HealthCheck(
        status=(
            "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"
        ),
        version=settings.app_version,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """Kubernetes readiness probe."""
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe."""
    return {"live": True}


@router.get("/runtime", response_model=RuntimeStatus)
async def runtime_status() -> RuntimeStatus:
    """Expose live/demo mode and provider readiness for OSS operators."""
    return RuntimeStatus(
        environment=settings.environment,
        cloud_sync_mode=settings.cloud_sync_mode,
        allow_live_cloud_sync=settings.allow_live_cloud_sync,
        default_demo_provider=settings.default_demo_provider,
        default_demo_scenario=settings.default_demo_scenario,
        llm_provider=settings.llm_provider,
        llm_configured=bool(settings.llm_api_key),
        providers=_build_provider_statuses(),
    )


@router.get("/preflight/{provider}", response_model=ProviderPreflightResult)
async def provider_preflight(provider: str) -> ProviderPreflightResult:
    """Run an actionable live-provider preflight for OSS operators."""
    provider_name = provider.lower()
    provider_class = LIVE_PROVIDER_CLASSES.get(provider_name)
    if provider_class is None:
        raise HTTPException(status_code=404, detail=f"Unsupported provider: {provider_name}")

    metadata = _provider_preflight_metadata()[provider_name]
    missing_env = _provider_missing_env(provider_name)
    checks = [
        ProviderPreflightCheck(
            name="credential_env",
            status="passed" if not missing_env else "failed",
            detail=(
                f"Credential source: {metadata['credential_source']}"
                if not missing_env
                else f"Missing env: {', '.join(missing_env)}"
            ),
        ),
        ProviderPreflightCheck(
            name="cost_source",
            status="passed" if not missing_env else "warning",
            detail=f"Live incurred costs come from {metadata['cost_source']}.",
        ),
    ]

    if missing_env:
        return ProviderPreflightResult(
            provider=provider_name,
            configured=False,
            ready=False,
            credential_source=metadata["credential_source"],
            cost_source=metadata["cost_source"],
            missing_env=missing_env,
            checks=checks,
        )

    live_provider = provider_class({})
    try:
        result = await live_provider.validate_live_access()
    except Exception as exc:
        checks.append(
            ProviderPreflightCheck(
                name="live_connection",
                status="failed",
                detail=str(exc),
            )
        )
        return ProviderPreflightResult(
            provider=provider_name,
            configured=True,
            ready=False,
            credential_source=metadata["credential_source"],
            cost_source=metadata["cost_source"],
            missing_env=[],
            checks=checks,
        )

    checks.append(
        ProviderPreflightCheck(
            name="live_connection",
            status="passed",
            detail=result.get("detail", "Live provider validation succeeded."),
        )
    )
    return ProviderPreflightResult(
        provider=provider_name,
        configured=True,
        ready=True,
        credential_source=metadata["credential_source"],
        cost_source=metadata["cost_source"],
        missing_env=[],
        checks=checks,
    )
