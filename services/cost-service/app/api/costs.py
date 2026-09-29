"""
CloudPulse AI - Cost Service
Cost data endpoints - querying and aggregations.
"""
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from collections import defaultdict
from io import StringIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.cache import RedisCache, get_cache
from app.core.database import get_db
from app.core.security import decrypt_credentials
from app.models import CloudAccount, CostRecord, User
from app.schemas import (
    CostRecordResponse,
    CostSummary,
    CostTrend,
    PaginatedResponse,
)
from app.services.currency import normalize_currency
from app.services.providers.factory import ProviderFactory

router = APIRouter()


class CostReconciliationResponse(BaseModel):
    """Comparison between imported CloudPulse totals and the upstream provider totals."""

    account_id: str
    account_name: str
    provider: str
    days: int
    currency: str | None = None
    last_sync_at: datetime | None = None
    imported_total: Decimal
    provider_total: Decimal
    variance_amount: Decimal
    variance_percent: Decimal
    status: str
    provider_mode: str


def _build_cost_filters(
    organization_id: str,
    start_date: datetime,
    end_date: datetime,
    account_id: str | None = None,
    provider: str | None = None,
    service: str | None = None,
    region: str | None = None,
    business_unit: str | None = None,
    environment: str | None = None,
    cost_center: str | None = None,
) -> list[ColumnElement[bool]]:
    """Build the shared filter list used across cost aggregation queries."""
    filters: list[ColumnElement[bool]] = [
        CloudAccount.organization_id == organization_id,
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    ]

    if account_id:
        filters.append(CostRecord.cloud_account_id == account_id)

    if provider:
        filters.append(CloudAccount.provider == provider)

    if service:
        filters.append(CostRecord.service == service)

    if region:
        filters.append(CostRecord.region == region)

    if business_unit:
        filters.append(CloudAccount.business_unit == business_unit)

    if environment:
        filters.append(CloudAccount.environment == environment)

    if cost_center:
        filters.append(CloudAccount.cost_center == cost_center)

    return filters


def _stored_currency(value: object) -> str:
    """Normalize legacy records without ever presenting malformed data as USD."""
    try:
        return normalize_currency(value, required=False)
    except ValueError:
        return "UNKNOWN"


def _resolve_window(days: int) -> tuple[datetime, datetime]:
    """Return a UTC time window spanning the requested number of days."""
    current_time = datetime.now(timezone.utc)
    start_date = (current_time - timedelta(days=days - 1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    end_date = current_time
    return start_date, end_date


async def _get_account_for_org(
    db: AsyncSession,
    *,
    organization_id: str,
    account_id: str,
) -> CloudAccount:
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == account_id,
            CloudAccount.organization_id == organization_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Cloud account not found")
    return account


@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    provider: str | None = None,
    service: str | None = None,
    region: str | None = None,
    business_unit: str | None = None,
    environment: str | None = None,
    cost_center: str | None = None,
) -> CostSummary:
    """Get aggregated cost summary for the specified period."""
    # Generate cache key with organization isolation
    cache_key = cache.generate_key(
        "summary",
        current_user.organization_id,
        account_id or "all",
        str(days),
        provider or "all",
        service or "all",
        region or "all",
        business_unit or "all",
        environment or "all",
        cost_center or "all",
    )
    
    # Check cache
    cached = await cache.get(cache_key)
    if cached:
        return CostSummary(**cached)
    
    # Calculate date range
    start_date, end_date = _resolve_window(days)
    filters = _build_cost_filters(
        current_user.organization_id,
        start_date,
        end_date,
        account_id=account_id,
        provider=provider,
        service=service,
        region=region,
        business_unit=business_unit,
        environment=environment,
        cost_center=cost_center,
    )

    day_bucket = func.date_trunc("day", CostRecord.date)
    currency_rows = (
        await db.execute(
            select(
                CostRecord.currency,
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters)
            .group_by(CostRecord.currency)
        )
    ).all()
    currency_totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in currency_rows:
        if row.total is not None:
            currency_totals[_stored_currency(row.currency)] += Decimal(str(row.total))
    currencies = sorted(currency_totals)

    service_rows = (
        await db.execute(
            select(
                CostRecord.service,
                CostRecord.currency,
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters)
            .group_by(CostRecord.service, CostRecord.currency)
            .order_by(func.sum(CostRecord.amount).desc())
        )
    ).all()

    region_rows = (
        await db.execute(
            select(
                CostRecord.region,
                CostRecord.currency,
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters, CostRecord.region.isnot(None))
            .group_by(CostRecord.region, CostRecord.currency)
            .order_by(func.sum(CostRecord.amount).desc())
        )
    ).all()

    day_rows = (
        await db.execute(
            select(
                day_bucket.label("day"),
                CostRecord.currency,
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters)
            .group_by(day_bucket, CostRecord.currency)
            .order_by(day_bucket)
        )
    ).all()

    by_service_by_currency: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for service_row in service_rows:
        if service_row.service and service_row.total is not None:
            by_service_by_currency[service_row.service][_stored_currency(service_row.currency)] = Decimal(str(service_row.total))

    by_region_by_currency: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for region_row in region_rows:
        if region_row.region and region_row.total is not None:
            by_region_by_currency[region_row.region][_stored_currency(region_row.currency)] = Decimal(str(region_row.total))

    by_day_by_currency: dict[object, dict[str, Decimal]] = defaultdict(dict)
    for row in day_rows:
        if row.day is not None and row.total is not None:
            day_value = row.day.date() if hasattr(row.day, "date") else row.day
            by_day_by_currency[day_value][_stored_currency(row.currency)] = Decimal(str(row.total))

    single_currency = len(currencies) == 1
    display_currency = currencies[0] if single_currency else None
    by_service = (
        {name: values[display_currency] for name, values in by_service_by_currency.items() if display_currency in values}
        if display_currency
        else {}
    )
    by_region = (
        {name: values[display_currency] for name, values in by_region_by_currency.items() if display_currency in values}
        if display_currency
        else {}
    )

    sorted_days = []
    for day_offset in range(days):
        current_day = (start_date + timedelta(days=day_offset)).date()
        day_values = by_day_by_currency.get(current_day, {})
        if single_currency and display_currency:
            sorted_days.append(
                {
                    "date": current_day.isoformat(),
                    "amount": float(day_values.get(display_currency, Decimal("0"))),
                    "currency": display_currency,
                }
            )
        elif currencies:
            for currency in currencies:
                sorted_days.append(
                    {
                        "date": current_day.isoformat(),
                        "amount": float(day_values.get(currency, Decimal("0"))),
                        "currency": currency,
                    }
                )

    summary = CostSummary(
        total_cost=currency_totals[display_currency] if single_currency and display_currency else None,
        currency=display_currency,
        currency_totals=dict(currency_totals),
        period_start=start_date,
        period_end=end_date,
        by_service=by_service,
        by_service_by_currency={name: dict(values) for name, values in by_service_by_currency.items()},
        by_region=by_region,
        by_region_by_currency={name: dict(values) for name, values in by_region_by_currency.items()},
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
    provider: str | None = None,
    business_unit: str | None = None,
    environment: str | None = None,
    cost_center: str | None = None,
    granularity: Literal["daily"] = "daily",
) -> list[CostTrend]:
    """Get cost trend data for visualization."""
    cache_key = cache.generate_key(
        "trend", 
        current_user.organization_id,
        account_id or "all", 
        str(days), 
        granularity,
        provider or "all",
        business_unit or "all",
        environment or "all",
        cost_center or "all",
    )
    
    cached = await cache.get(cache_key)
    if cached:
        return [CostTrend(**item) for item in cached]
    
    start_date, end_date = _resolve_window(days)
    filters = _build_cost_filters(
        current_user.organization_id,
        start_date,
        end_date,
        account_id=account_id,
        provider=provider,
        business_unit=business_unit,
        environment=environment,
        cost_center=cost_center,
    )
    
    bucket = func.date_trunc("day", CostRecord.date)

    rows = (
        await db.execute(
            select(
                bucket.label("day"),
                CostRecord.currency,
                func.sum(CostRecord.amount).label("total"),
            )
            .join(CloudAccount)
            .where(*filters)
            .group_by(bucket, CostRecord.currency)
            .order_by(bucket)
        )
    ).all()
    amounts_by_currency: dict[str, dict[object, Decimal]] = defaultdict(dict)
    for row in rows:
        if row.day is not None and row.total is not None:
            day_value = row.day.date() if hasattr(row.day, "date") else row.day
            amounts_by_currency[_stored_currency(row.currency)][day_value] = Decimal(str(row.total))

    trends: list[CostTrend] = []
    for currency in sorted(amounts_by_currency):
        previous: Decimal | None = None
        daily_amounts = amounts_by_currency[currency]
        for day_offset in range(days):
            current_day = (start_date + timedelta(days=day_offset)).date()
            amount = daily_amounts.get(current_day, Decimal("0"))
            change_percent = None
            if previous is not None and previous > 0:
                change_percent = ((amount - previous) / previous) * 100
            trends.append(
                CostTrend(
                    date=datetime.combine(current_day, datetime.min.time(), tzinfo=timezone.utc),
                    amount=amount,
                    currency=currency,
                    change_percent=change_percent,
                    predicted=False,
                )
            )
            previous = amount
    
    # Cache result
    await cache.set(cache_key, [t.model_dump(mode="json") for t in trends])
    
    return trends


@router.get("/by-service")
async def get_costs_by_service(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    account_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    provider: str | None = None,
    business_unit: str | None = None,
    environment: str | None = None,
    cost_center: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict]:
    """Get top services by cost."""
    start_date, end_date = _resolve_window(days)
    filters = _build_cost_filters(
        current_user.organization_id,
        start_date,
        end_date,
        account_id=account_id,
        provider=provider,
        business_unit=business_unit,
        environment=environment,
        cost_center=cost_center,
    )

    query = select(
        CostRecord.service,
        CostRecord.currency,
        func.sum(CostRecord.amount).label("total_cost"),
        func.count(CostRecord.id).label("record_count"),
    ).join(CloudAccount).where(*filters)

    # Group by currency before ordering; unlike currencies are never ranked as one total.
    query = query.group_by(
        CostRecord.service,
        CostRecord.currency,
    ).order_by(
        func.sum(CostRecord.amount).desc()
    ).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "service": row.service,
            "total_cost": float(row.total_cost) if row.total_cost else 0,
            "currency": _stored_currency(row.currency),
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
    provider: str | None = None,
    business_unit: str | None = None,
    environment: str | None = None,
    cost_center: str | None = None,
) -> list[dict]:
    """Get costs grouped by region."""
    start_date, end_date = _resolve_window(days)
    filters = _build_cost_filters(
        current_user.organization_id,
        start_date,
        end_date,
        account_id=account_id,
        provider=provider,
        business_unit=business_unit,
        environment=environment,
        cost_center=cost_center,
    )

    query = select(
        CostRecord.region,
        CostRecord.currency,
        func.sum(CostRecord.amount).label("total_cost"),
    ).join(CloudAccount).where(*filters, CostRecord.region.isnot(None))

    # Group by currency before ordering; each response row is denominated.
    query = query.group_by(
        CostRecord.region,
        CostRecord.currency,
    ).order_by(
        func.sum(CostRecord.amount).desc()
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "region": row.region,
            "total_cost": float(row.total_cost) if row.total_cost else 0,
            "currency": _stored_currency(row.currency),
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
    provider: str | None = None,
    business_unit: str | None = None,
    environment: str | None = None,
    cost_center: str | None = None,
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

    if provider:
        query = query.where(CloudAccount.provider == provider)
        count_query = count_query.where(CloudAccount.provider == provider)

    if business_unit:
        query = query.where(CloudAccount.business_unit == business_unit)
        count_query = count_query.where(CloudAccount.business_unit == business_unit)

    if environment:
        query = query.where(CloudAccount.environment == environment)
        count_query = count_query.where(CloudAccount.environment == environment)

    if cost_center:
        query = query.where(CloudAccount.cost_center == cost_center)
        count_query = count_query.where(CloudAccount.cost_center == cost_center)
    
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


@router.get("/reconciliation", response_model=CostReconciliationResponse)
async def get_cost_reconciliation(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    account_id: str = Query(..., description="Cloud account id to reconcile"),
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> CostReconciliationResponse:
    """Compare imported CloudPulse totals with a fresh provider query for the same account."""
    account = await _get_account_for_org(
        db,
        organization_id=current_user.organization_id,
        account_id=account_id,
    )
    start_date, end_date = _resolve_window(days)

    imported_rows = (
        await db.execute(
            select(
                CostRecord.currency,
                func.sum(CostRecord.amount).label("total"),
            )
            .where(
                CostRecord.cloud_account_id == account.id,
                CostRecord.date >= start_date,
                CostRecord.date <= end_date,
            )
            .group_by(CostRecord.currency)
        )
    ).all()
    imported_by_currency: dict[str, Decimal] = defaultdict(Decimal)
    for row in imported_rows:
        if row.total is not None:
            imported_by_currency[_stored_currency(row.currency)] += Decimal(str(row.total))

    credentials = decrypt_credentials(account.credentials or {})
    provider = ProviderFactory.get_provider(
        account.provider,
        credentials,
        organization_id=current_user.organization_id,
    )
    provider_records = await provider.get_cost_data(start_date=start_date, end_date=end_date, granularity="DAILY")
    provider_by_currency: dict[str, Decimal] = defaultdict(Decimal)
    try:
        for provider_record in provider_records:
            provider_currency = normalize_currency(provider_record.get("currency"))
            provider_by_currency[provider_currency] += Decimal(str(provider_record.get("amount", 0)))
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Provider reconciliation data has an invalid amount or currency.",
        ) from exc

    currencies = sorted(set(imported_by_currency) | set(provider_by_currency))
    if len(currencies) > 1:
        raise HTTPException(
            status_code=409,
            detail="Reconciliation requires one matching currency for imported and provider data.",
        )
    currency = currencies[0] if currencies else None
    imported_total_decimal = (imported_by_currency.get(currency, Decimal("0")) if currency else Decimal("0")).quantize(Decimal("0.01"))
    provider_total_decimal = (provider_by_currency.get(currency, Decimal("0")) if currency else Decimal("0")).quantize(Decimal("0.01"))

    variance_amount = (imported_total_decimal - provider_total_decimal).quantize(Decimal("0.01"))
    if provider_total_decimal > 0:
        variance_percent = ((variance_amount / provider_total_decimal) * 100).quantize(Decimal("0.01"))
    else:
        variance_percent = Decimal("0.00")

    tolerance = max(Decimal("1.00"), provider_total_decimal * Decimal("0.01"))
    status = "matched" if abs(variance_amount) <= tolerance else "drift"

    return CostReconciliationResponse(
        account_id=account.id,
        account_name=account.account_name,
        provider=account.provider,
        days=days,
        currency=currency,
        last_sync_at=account.last_sync_at,
        imported_total=imported_total_decimal,
        provider_total=provider_total_decimal,
        variance_amount=variance_amount,
        variance_percent=variance_percent,
        status=status,
        provider_mode=str(getattr(provider, "mode", credentials.get("mode", "live"))),
    )


@router.get("/export")
async def export_cost_records(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    account_id: str | None = None,
    provider: str | None = None,
    business_unit: str | None = None,
    environment: str | None = None,
    cost_center: str | None = None,
    service: str | None = None,
    region: str | None = None,
) -> StreamingResponse:
    """Export filtered cost records as CSV."""
    start_date, end_date = _resolve_window(days)
    filters = _build_cost_filters(
        current_user.organization_id,
        start_date,
        end_date,
        account_id=account_id,
        provider=provider,
        service=service,
        region=region,
        business_unit=business_unit,
        environment=environment,
        cost_center=cost_center,
    )

    rows = (
        await db.execute(
            select(
                CostRecord.date,
                CloudAccount.provider,
                CloudAccount.account_name,
                CloudAccount.account_id,
                CloudAccount.business_unit,
                CloudAccount.environment,
                CloudAccount.cost_center,
                CostRecord.service,
                CostRecord.region,
                CostRecord.amount,
                CostRecord.currency,
            )
            .join(CloudAccount)
            .where(*filters)
            .order_by(CostRecord.date.desc(), CloudAccount.account_name, CostRecord.service)
        )
    ).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "provider",
            "account_name",
            "account_id",
            "business_unit",
            "environment",
            "cost_center",
            "service",
            "region",
            "amount",
            "currency",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.date.isoformat() if row.date else "",
                row.provider,
                row.account_name,
                row.account_id,
                row.business_unit or "",
                row.environment or "",
                row.cost_center or "",
                row.service,
                row.region or "",
                str(row.amount),
                row.currency,
            ]
        )

    filename = f"cloudpulse-costs-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
