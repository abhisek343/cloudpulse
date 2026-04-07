"""
CloudPulse AI - Cost Service
Cloud Accounts management endpoints.
"""
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import boto3
from anyio import to_thread
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.events import publish_sync_task
from app.core.security import encrypt_credentials
from app.models import CloudAccount, User
from app.schemas import (
    CloudAccountDetectRequest,
    CloudAccountDetectResponse,
    CloudAccountCreate,
    CloudAccountResponse,
    CloudAccountStatusResponse,
    CloudAccountUpdate,
    PaginatedResponse,
)
from app.services.providers.azure import AzureProvider
from app.services.providers.gcp import GCPProvider

router = APIRouter()
settings = get_settings()


def normalize_account_id(account_id: str) -> str:
    """Validate account UUIDs before querying PostgreSQL UUID columns."""
    try:
        return str(UUID(account_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cloud account {account_id} not found",
        ) from exc


async def get_cloud_account_or_404(
    db: AsyncSession,
    *,
    account_id: str,
    organization_id: str,
) -> CloudAccount:
    """Load an account within the caller organization or raise 404."""
    normalized_account_id = normalize_account_id(account_id)
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == normalized_account_id,
            CloudAccount.organization_id == organization_id,
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cloud account {account_id} not found",
        )

    return account


async def build_cloud_account_status(
    db: AsyncSession,
    account: CloudAccount,
) -> CloudAccountStatusResponse:
    """Return sync telemetry and imported-data coverage for an account."""
    from app.models import CostRecord

    summary = await db.execute(
        select(
            func.count(CostRecord.id).label("total_records"),
            func.min(CostRecord.date).label("coverage_start"),
            func.max(CostRecord.date).label("coverage_end"),
            func.count(func.distinct(CostRecord.service)).label("services_detected"),
            func.min(CostRecord.currency).label("currency"),
        ).where(CostRecord.cloud_account_id == account.id)
    )
    row = summary.one()

    return CloudAccountStatusResponse(
        account_id=account.id,
        is_active=account.is_active,
        last_sync_at=account.last_sync_at,
        last_sync_status=account.last_sync_status,
        last_sync_error=account.last_sync_error,
        last_sync_started_at=account.last_sync_started_at,
        last_sync_completed_at=account.last_sync_completed_at,
        last_sync_records_imported=account.last_sync_records_imported,
        total_records=row.total_records or 0,
        coverage_start=row.coverage_start,
        coverage_end=row.coverage_end,
        services_detected=row.services_detected or 0,
        currency=row.currency,
    )


async def detect_cloud_account_metadata(
    provider: str,
    credentials: dict | None,
) -> CloudAccountDetectResponse:
    """Suggest provider metadata so onboarding can prefill, then ask the user to confirm."""
    credentials = credentials or {}

    if provider == "demo":
        scenario = str(credentials.get("scenario") or settings.default_demo_scenario)
        simulated_provider = str(credentials.get("simulated_provider") or settings.default_demo_provider)
        return CloudAccountDetectResponse(
            provider=provider,
            account_id=f"demo-{scenario}-001",
            account_name=f"Demo {scenario.upper()} Workspace",
            confidence="high",
            note="Detected from the selected demo preset.",
            detected_metadata={
                "scenario": scenario,
                "simulated_provider": simulated_provider,
            },
        )

    if provider == "aws":
        session = boto3.Session(
            aws_access_key_id=credentials.get("access_key_id") or settings.aws_access_key_id,
            aws_secret_access_key=credentials.get("secret_access_key") or settings.aws_secret_access_key,
            aws_session_token=credentials.get("session_token") or settings.aws_session_token,
            region_name=credentials.get("region") or settings.aws_region,
        )
        sts_client = session.client("sts")
        identity = await to_thread.run_sync(sts_client.get_caller_identity)
        account_id = str(identity.get("Account") or "").strip()
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to detect the AWS account ID from the current credentials.",
            )
        return CloudAccountDetectResponse(
            provider=provider,
            account_id=account_id,
            account_name=f"AWS account {account_id}",
            confidence="high",
            note="Detected with AWS STS. Review the name before saving.",
            detected_metadata={
                "caller_arn": str(identity.get("Arn") or ""),
                "region": credentials.get("region") or settings.aws_region,
            },
        )

    if provider == "azure":
        azure_provider = AzureProvider(credentials)
        azure_provider._require_credentials()
        subscription_id = str(azure_provider.subscription_id)
        tenant_id = str(azure_provider.tenant_id)
        subscription_name = str(
            credentials.get("subscription_name")
            or credentials.get("display_name")
            or f"Azure subscription {subscription_id[:8]}"
        )
        return CloudAccountDetectResponse(
            provider=provider,
            account_id=subscription_id,
            account_name=subscription_name,
            confidence="medium",
            note="Derived from the configured Azure subscription credentials. Confirm the friendly name.",
            detected_metadata={"tenant_id": tenant_id},
        )

    if provider == "gcp":
        gcp_provider = GCPProvider(credentials)
        gcp_provider._require_credentials()
        project_id = str(gcp_provider.project_id or "")
        billing_account_id = str(gcp_provider.billing_account_id or "")
        account_id = billing_account_id or project_id
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide a GCP billing account or project ID so CloudPulse can identify this source.",
            )
        account_name = (
            f"GCP billing {billing_account_id}"
            if billing_account_id
            else f"GCP project {project_id}"
        )
        detected_metadata = {}
        if project_id:
            detected_metadata["project_id"] = project_id
        if billing_account_id:
            detected_metadata["billing_account_id"] = billing_account_id
        service_account_email = gcp_provider.service_account_info.get("client_email") if gcp_provider.service_account_info else None
        if service_account_email:
            detected_metadata["service_account"] = str(service_account_email)
        return CloudAccountDetectResponse(
            provider=provider,
            account_id=account_id,
            account_name=account_name,
            confidence="medium",
            note="Derived from the configured GCP billing export settings. Confirm the identifier before saving.",
            detected_metadata=detected_metadata,
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unsupported provider: {provider}")


@router.get("/", response_model=PaginatedResponse)
async def list_cloud_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    provider: str | None = None,
    is_active: bool | None = None,
) -> PaginatedResponse:
    """List all cloud accounts with pagination and filtering."""
    # Build query with organization isolation
    query = select(CloudAccount).where(CloudAccount.organization_id == current_user.organization_id)
    count_query = select(func.count(CloudAccount.id)).where(
        CloudAccount.organization_id == current_user.organization_id
    )
    
    if provider:
        query = query.where(CloudAccount.provider == provider)
        count_query = count_query.where(CloudAccount.provider == provider)
    
    if is_active is not None:
        query = query.where(CloudAccount.is_active == is_active)
        count_query = count_query.where(CloudAccount.is_active == is_active)
    
    # Get total count
    total = await db.scalar(count_query) or 0
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(CloudAccount.created_at.desc())
    
    result = await db.execute(query)
    accounts = result.scalars().all()
    
    return PaginatedResponse(
        items=[CloudAccountResponse.model_validate(acc) for acc in accounts],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("/", response_model=CloudAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_cloud_account(
    account_data: CloudAccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CloudAccountResponse:
    """Create a new cloud account connection."""
    # Check for duplicate within organization
    existing = await db.execute(
        select(CloudAccount).where(
            CloudAccount.organization_id == current_user.organization_id,
            CloudAccount.provider == account_data.provider.value,
            CloudAccount.account_id == account_data.account_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account {account_data.account_id} already exists for provider {account_data.provider}",
        )
    
    # Create account
    account = CloudAccount(
        organization_id=current_user.organization_id,
        provider=account_data.provider.value,
        account_id=account_data.account_id,
        account_name=account_data.account_name,
        business_unit=account_data.business_unit,
        environment=account_data.environment,
        cost_center=account_data.cost_center,
        credentials=encrypt_credentials(account_data.credentials),
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    
    return CloudAccountResponse.model_validate(account)


@router.post("/detect", response_model=CloudAccountDetectResponse)
async def detect_cloud_account(
    request: CloudAccountDetectRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> CloudAccountDetectResponse:
    """Detect provider-backed account metadata so the UI can prefill fields."""
    del current_user
    try:
        return await detect_cloud_account_metadata(request.provider.value, request.credentials)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CloudPulse could not detect the account from the provided settings: {exc}",
        ) from exc


@router.get("/{account_id}", response_model=CloudAccountResponse)
async def get_cloud_account(
    account_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CloudAccountResponse:
    """Get a specific cloud account by ID."""
    account = await get_cloud_account_or_404(
        db,
        account_id=account_id,
        organization_id=current_user.organization_id,
    )
    return CloudAccountResponse.model_validate(account)


@router.get("/{account_id}/status", response_model=CloudAccountStatusResponse)
async def get_cloud_account_status(
    account_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CloudAccountStatusResponse:
    """Get sync telemetry and imported-data coverage for one account."""
    account = await get_cloud_account_or_404(
        db,
        account_id=account_id,
        organization_id=current_user.organization_id,
    )
    return await build_cloud_account_status(db, account)


@router.patch("/{account_id}", response_model=CloudAccountResponse)
async def update_cloud_account(
    account_id: str,
    update_data: CloudAccountUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CloudAccountResponse:
    """Update a cloud account."""
    account = await get_cloud_account_or_404(
        db,
        account_id=account_id,
        organization_id=current_user.organization_id,
    )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if field == "credentials":
            value = encrypt_credentials(value)
        setattr(account, field, value)
    
    await db.flush()
    await db.refresh(account)
    
    return CloudAccountResponse.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloud_account(
    account_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a cloud account."""
    account = await get_cloud_account_or_404(
        db,
        account_id=account_id,
        organization_id=current_user.organization_id,
    )
    await db.delete(account)


@router.post("/{account_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_cost_sync(
    account_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a cost data sync for a cloud account."""
    account = await get_cloud_account_or_404(
        db,
        account_id=account_id,
        organization_id=current_user.organization_id,
    )
    normalized_account_id = account.id
    account.last_sync_status = "queued"
    account.last_sync_error = None
    account.last_sync_started_at = datetime.now(UTC)
    account.last_sync_completed_at = None
    account.last_sync_records_imported = None

    # Publish sync task to RabbitMQ
    task = {
        "type": "sync_account",
        "account_id": normalized_account_id,
        "days": 30
    }
    background_tasks.add_task(publish_sync_task, task)

    return {
        "message": "Cost sync initiated",
        "account_id": normalized_account_id,
        "status": "pending",
    }
