"""
CloudPulse AI - Cost Service
Cloud Accounts management endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import CloudAccount
from app.schemas import (
    CloudAccountCreate,
    CloudAccountResponse,
    CloudAccountUpdate,
    PaginatedResponse,
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_cloud_accounts(
    db: AsyncSession = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    provider: str | None = None,
    is_active: bool | None = None,
) -> PaginatedResponse:
    """List all cloud accounts with pagination and filtering."""
    # Build query
    query = select(CloudAccount)
    count_query = select(func.count(CloudAccount.id))
    
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
    db: AsyncSession = Depends(get_db),
    # TODO: Add auth dependency to get organization_id from current user
) -> CloudAccountResponse:
    """Create a new cloud account connection."""
    # For now, use a placeholder organization_id (will be replaced with auth)
    organization_id = "00000000-0000-0000-0000-000000000000"
    
    # Check for duplicate
    existing = await db.execute(
        select(CloudAccount).where(
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
        organization_id=organization_id,
        provider=account_data.provider.value,
        account_id=account_data.account_id,
        account_name=account_data.account_name,
        credentials=account_data.credentials,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    
    return CloudAccountResponse.model_validate(account)


@router.get("/{account_id}", response_model=CloudAccountResponse)
async def get_cloud_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> CloudAccountResponse:
    """Get a specific cloud account by ID."""
    result = await db.execute(
        select(CloudAccount).where(CloudAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cloud account {account_id} not found",
        )
    
    return CloudAccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=CloudAccountResponse)
async def update_cloud_account(
    account_id: str,
    update_data: CloudAccountUpdate,
    db: AsyncSession = Depends(get_db),
) -> CloudAccountResponse:
    """Update a cloud account."""
    result = await db.execute(
        select(CloudAccount).where(CloudAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cloud account {account_id} not found",
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(account, field, value)
    
    await db.flush()
    await db.refresh(account)
    
    return CloudAccountResponse.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloud_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a cloud account."""
    result = await db.execute(
        select(CloudAccount).where(CloudAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cloud account {account_id} not found",
        )
    
    await db.delete(account)


@router.post("/{account_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_cost_sync(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a cost data sync for a cloud account."""
    result = await db.execute(
        select(CloudAccount).where(CloudAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cloud account {account_id} not found",
        )
    
    # TODO: Publish sync task to RabbitMQ
    # For now, return accepted status
    return {
        "message": "Cost sync initiated",
        "account_id": account_id,
        "status": "pending",
    }
