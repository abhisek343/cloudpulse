"""
CloudPulse AI - Cost Service
Chat API endpoints for AI analyst features.
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models import CloudAccount, CostRecord, User
from app.services.llm_service import LLMService, get_llm_service

router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat analysis."""
    message: str
    context_keys: dict[str, str] = Field(default_factory=dict)
    time_range: str = "last_30_days"


class ChatResponse(BaseModel):
    """Response model for chat analysis."""
    response: str
    provider: str
    model: str


def _resolve_time_range_days(time_range: str) -> int:
    """Map a chat time-range token to a supported day window."""
    return {
        "last_7_days": 7,
        "last_30_days": 30,
        "last_90_days": 90,
    }.get(time_range, 30)


@router.post("/analyze", response_model=ChatResponse)
async def analyze_cost_chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    llm_service: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    """
    Analyze cloud costs using AI based on user query.
    
    This endpoint:
    1. Fetches recent cost summary (context)
    2. Sends the context + user question to the LLM
    3. Returns the natural language response
    """
    if not settings.llm_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM service not configured. Please set LLM_API_KEY."
        )

    days = _resolve_time_range_days(request.time_range)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days - 1)
    provider_filter = request.context_keys.get("provider")
    account_id = request.context_keys.get("account_id")

    filters: list[object] = [
        CloudAccount.organization_id == current_user.organization_id,
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    ]

    if provider_filter and provider_filter.lower() != "all":
        filters.append(CloudAccount.provider == provider_filter.lower())

    if account_id and account_id.lower() != "all":
        filters.append(CostRecord.cloud_account_id == account_id)

    total_cost = await db.scalar(
        select(func.coalesce(func.sum(CostRecord.amount), 0))
        .join(CloudAccount)
        .where(*filters)
    )
    total_records = await db.scalar(
        select(func.count(CostRecord.id))
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
            .limit(5)
        )
    ).all()

    day_bucket = func.date_trunc("day", CostRecord.date)
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

    context: dict[str, Any] = {
        "period": f"Last {days} Days",
        "provider": provider_filter.upper() if provider_filter else "ALL",
        "account_id": account_id or "all",
        "total_cost": float(total_cost or 0),
        "records_found": int(total_records or 0),
        "top_services": [
            {
                "service": row.service,
                "amount": float(row.total),
            }
            for row in service_rows
            if row.service and row.total is not None
        ],
        "daily_trend": [
            {
                "date": row.day.date().isoformat(),
                "amount": float(row.total),
            }
            for row in day_rows
            if row.day is not None and row.total is not None
        ][-7:],
    }

    if not context["records_found"]:
        context["note"] = (
            "No stored cost records matched this tenant and filter set. "
            "Answer conservatively and say when more billing history is needed."
        )

    # 2. Get AI Response
    response_text = await llm_service.get_chat_response(
        message=request.message,
        context_data=context
    )
    
    return ChatResponse(
        response=response_text,
        provider=settings.llm_provider,
        model=settings.llm_model
    )
