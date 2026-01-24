"""
CloudPulse AI - Cost Service
Cost data endpoints - querying and aggregations.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache, get_cache
from app.core.database import get_db
from app.models import CloudAccount, CostRecord
from app.schemas import (
    CostRecordResponse,
    CostSummary,
    CostTrend,
    PaginatedResponse,
)

router = APIRouter()


@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    service: str | None = None,
    region: str | None = None,
) -> CostSummary:
    """Get aggregated cost summary for the specified period."""
    # Generate cache key
    cache_key = cache.generate_key(
        "summary",
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
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Build base query
    query = select(CostRecord).where(
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    )
    
    if account_id:
        query = query.where(CostRecord.cloud_account_id == account_id)
    
    if service:
        query = query.where(CostRecord.service == service)
    
    if region:
        query = query.where(CostRecord.region == region)
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    # Aggregate data
    total_cost = Decimal("0")
    by_service: dict[str, Decimal] = {}
    by_region: dict[str, Decimal] = {}
    by_day: dict[str, Decimal] = {}
    
    for record in records:
        total_cost += record.amount
        
        # By service
        if record.service not in by_service:
            by_service[record.service] = Decimal("0")
        by_service[record.service] += record.amount
        
        # By region
        if record.region:
            if record.region not in by_region:
                by_region[record.region] = Decimal("0")
            by_region[record.region] += record.amount
        
        # By day
        day_key = record.date.strftime("%Y-%m-%d")
        if day_key not in by_day:
            by_day[day_key] = Decimal("0")
        by_day[day_key] += record.amount
    
    # Sort by_day
    sorted_days = [
        {"date": k, "amount": float(v)}
        for k, v in sorted(by_day.items())
    ]
    
    summary = CostSummary(
        total_cost=total_cost,
        currency="USD",
        period_start=start_date,
        period_end=end_date,
        by_service={k: v for k, v in sorted(by_service.items(), key=lambda x: x[1], reverse=True)},
        by_region={k: v for k, v in sorted(by_region.items(), key=lambda x: x[1], reverse=True)},
        by_day=sorted_days,
    )
    
    # Cache result
    await cache.set(cache_key, summary.model_dump(mode="json"))
    
    return summary


@router.get("/trend", response_model=list[CostTrend])
async def get_cost_trend(
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    granularity: str = "daily",
) -> list[CostTrend]:
    """Get cost trend data for visualization."""
    cache_key = cache.generate_key("trend", account_id or "all", str(days), granularity)
    
    cached = await cache.get(cache_key)
    if cached:
        return [CostTrend(**item) for item in cached]
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Query daily costs
    query = select(
        func.date_trunc("day", CostRecord.date).label("day"),
        func.sum(CostRecord.amount).label("total"),
    ).where(
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    ).group_by(
        func.date_trunc("day", CostRecord.date)
    ).order_by("day")
    
    if account_id:
        query = query.where(CostRecord.cloud_account_id == account_id)
    
    result = await db.execute(query)
    rows = result.all()
    
    trends: list[CostTrend] = []
    prev_amount: Decimal | None = None
    
    for row in rows:
        amount = Decimal(str(row.total)) if row.total else Decimal("0")
        change_percent = None
        
        if prev_amount is not None and prev_amount > 0:
            change_percent = ((amount - prev_amount) / prev_amount) * 100
        
        trends.append(CostTrend(
            date=row.day,
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
    db: AsyncSession = Depends(get_db),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict]:
    """Get top services by cost."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Build base query with all filters BEFORE grouping/limit
    query = select(
        CostRecord.service,
        func.sum(CostRecord.amount).label("total_cost"),
        func.count(CostRecord.id).label("record_count"),
    ).where(
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    )
    
    # Apply account filter BEFORE grouping
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
    db: AsyncSession = Depends(get_db),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[dict]:
    """Get costs grouped by region."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Build base query with all filters BEFORE grouping
    query = select(
        CostRecord.region,
        func.sum(CostRecord.amount).label("total_cost"),
    ).where(
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
        CostRecord.region.isnot(None),
    )
    
    # Apply account filter BEFORE grouping
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
    query = select(CostRecord)
    count_query = select(func.count(CostRecord.id))
    
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
