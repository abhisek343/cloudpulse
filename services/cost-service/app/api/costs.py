"""
CloudPulse AI - Cost Service
Cost data endpoints - querying and aggregations.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.cache import RedisCache, get_cache
from app.core.database import get_db
from app.models import CloudAccount, CostRecord, User
from app.schemas import (
    CostRecordResponse,
    CostSummary,
    CostTrend,
    PaginatedResponse,
)

router = APIRouter()


def _build_cost_filters(
    organization_id: str,
    start_date: datetime,
    end_date: datetime,
    account_id: str | None = None,
    service: str | None = None,
    region: str | None = None,
) -> list[object]:
    """Build the shared filter list used across cost aggregation queries."""
    filters: list[object] = [
        CloudAccount.organization_id == organization_id,
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    ]

    if account_id:
        filters.append(CostRecord.cloud_account_id == account_id)

    if service:
        filters.append(CostRecord.service == service)

    if region:
        filters.append(CostRecord.region == region)

    return filters


@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    service: str | None = None,
    region: str | None = None,
) -> CostSummary:
    """Get aggregated cost summary for the specified period."""
    # Generate cache key with organization isolation
    cache_key = cache.generate_key(
        "summary",
        current_user.organization_id,
        account_id or "all",
        str(days),
        service or "all",
        region or "all",
    )
    
    # Check cache
    cached = await cache.get(cache_key)
    if cached:
        return CostSummary(**cached)
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days - 1)
    filters = _build_cost_filters(
        current_user.organization_id,
        start_date,
        end_date,
        account_id=account_id,
        service=service,
        region=region,
    )

    day_bucket = func.date_trunc("day", CostRecord.date)
    total_cost = await db.scalar(
        select(func.coalesce(func.sum(CostRecord.amount), 0))
        .join(CloudAccount)
        .where(*filters)
    )

    service_rows = (
        await db.execute(
            select(
                CostRecord.service,
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters)
            .group_by(CostRecord.service)
            .order_by(func.sum(CostRecord.amount).desc())
        )
    ).all()

    region_rows = (
        await db.execute(
            select(
                CostRecord.region,
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters, CostRecord.region.isnot(None))
            .group_by(CostRecord.region)
            .order_by(func.sum(CostRecord.amount).desc())
        )
    ).all()

    day_rows = (
        await db.execute(
            select(
                day_bucket.label("day"),
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters)
            .group_by(day_bucket)
            .order_by(day_bucket)
        )
    ).all()

    by_service = {
        row.service: Decimal(str(row.total))
        for row in service_rows
        if row.service and row.total is not None
    }
    by_region = {
        row.region: Decimal(str(row.total))
        for row in region_rows
        if row.region and row.total is not None
    }

    by_day_lookup = {
        row.day.date(): Decimal(str(row.total))
        for row in day_rows
        if row.day is not None and row.total is not None
    }
    sorted_days = []
    for day_offset in range(days):
        current_day = (start_date + timedelta(days=day_offset)).date()
        sorted_days.append(
            {
                "date": current_day.isoformat(),
                "amount": float(by_day_lookup.get(current_day, Decimal("0"))),
            }
        )

    summary = CostSummary(
        total_cost=Decimal(str(total_cost or 0)),
        currency="USD",
        period_start=start_date,
        period_end=end_date,
        by_service=by_service,
        by_region=by_region,
        by_day=sorted_days,
    )
    
    # Cache result
    await cache.set(cache_key, summary.model_dump(mode="json"))
    
    return summary


@router.get("/trend", response_model=list[CostTrend])
async def get_cost_trend(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    granularity: Literal["daily"] = "daily",
) -> list[CostTrend]:
    """Get cost trend data for visualization."""
    cache_key = cache.generate_key(
        "trend", 
        current_user.organization_id,
        account_id or "all", 
        str(days), 
        granularity
    )
    
    cached = await cache.get(cache_key)
    if cached:
        return [CostTrend(**item) for item in cached]
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days - 1)
    filters = _build_cost_filters(
        current_user.organization_id,
        start_date,
        end_date,
        account_id=account_id,
    )
    
    bucket = func.date_trunc("day", CostRecord.date)

    rows = (
        await db.execute(
            select(
                bucket.label("day"),
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters)
            .group_by(bucket)
            .order_by(bucket)
        )
    ).all()
    amounts_by_day = {
        row.day.date(): Decimal(str(row.total))
        for row in rows
        if row.day is not None and row.total is not None
    }
    
    trends: list[CostTrend] = []
    prev_amount: Decimal | None = None
    
    for day_offset in range(days):
        current_day = (start_date + timedelta(days=day_offset)).date()
        amount = amounts_by_day.get(current_day, Decimal("0"))
        change_percent = None
        
        if prev_amount is not None and prev_amount > 0:
            change_percent = ((amount - prev_amount) / prev_amount) * 100
        
        trends.append(CostTrend(
            date=datetime.combine(current_day, datetime.min.time(), tzinfo=timezone.utc),
            amount=amount,
            change_percent=change_percent,
            predicted=False,
        ))
        prev_amount = amount
    
    # Cache result
    await cache.set(cache_key, [t.model_dump(mode="json") for t in trends])
    
    return trends


@router.get("/by-service")
async def get_costs_by_service(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict]:
    """Get top services by cost."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days - 1)
    
    # Build base query with organization isolation
    query = select(
        CostRecord.service,
        func.sum(CostRecord.amount).label("total_cost"),
        func.count(CostRecord.id).label("record_count"),
    ).join(CloudAccount).where(
        CloudAccount.organization_id == current_user.organization_id,
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    )
    
    # Apply account filter
    if account_id:
        query = query.where(CostRecord.cloud_account_id == account_id)
    
    # Group and order
    query = query.group_by(
        CostRecord.service
    ).order_by(
        func.sum(CostRecord.amount).desc()
    ).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "service": row.service,
            "total_cost": float(row.total_cost) if row.total_cost else 0,
            "record_count": row.record_count,
        }
        for row in rows
    ]


@router.get("/by-region")
async def get_costs_by_region(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[dict]:
    """Get costs grouped by region."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days - 1)
    
    # Build base query with organization isolation
    query = select(
        CostRecord.region,
        func.sum(CostRecord.amount).label("total_cost"),
    ).join(CloudAccount).where(
        CloudAccount.organization_id == current_user.organization_id,
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
        CostRecord.region.isnot(None),
    )
    
    # Apply account filter
    if account_id:
        query = query.where(CostRecord.cloud_account_id == account_id)
    
    # Group and order
    query = query.group_by(
        CostRecord.region
    ).order_by(
        func.sum(CostRecord.amount).desc()
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "region": row.region,
            "total_cost": float(row.total_cost) if row.total_cost else 0,
        }
        for row in rows
    ]


@router.get("/records", response_model=PaginatedResponse)
async def list_cost_records(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    account_id: str | None = None,
    service: str | None = None,
    region: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> PaginatedResponse:
    """List individual cost records with filtering and pagination."""
    query = select(CostRecord).join(CloudAccount).where(
        CloudAccount.organization_id == current_user.organization_id
    )
    count_query = select(func.count(CostRecord.id)).join(CloudAccount).where(
        CloudAccount.organization_id == current_user.organization_id
    )
    
    # Apply filters
    if account_id:
        query = query.where(CostRecord.cloud_account_id == account_id)
        count_query = count_query.where(CostRecord.cloud_account_id == account_id)
    
    if service:
        query = query.where(CostRecord.service == service)
        count_query = count_query.where(CostRecord.service == service)
    
    if region:
        query = query.where(CostRecord.region == region)
        count_query = count_query.where(CostRecord.region == region)
    
    if start_date:
        query = query.where(CostRecord.date >= start_date)
        count_query = count_query.where(CostRecord.date >= start_date)
    
    if end_date:
        query = query.where(CostRecord.date <= end_date)
        count_query = count_query.where(CostRecord.date <= end_date)
    
    # Get total
    total = await db.scalar(count_query) or 0
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(CostRecord.date.desc())
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    return PaginatedResponse(
        items=[CostRecordResponse.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
