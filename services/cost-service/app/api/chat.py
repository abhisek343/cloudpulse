"""
CloudPulse AI - Cost Service
Chat API endpoints for AI analyst features with multi-turn conversation memory.
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models import ChatMessage, CloudAccount, CostRecord, User
from app.services.audit_service import AuditService
from app.services.llm_service import LLMService, get_llm_service

router = APIRouter()

MAX_HISTORY_TURNS = 20


class ChatRequest(BaseModel):
    """Request model for chat analysis."""
    message: str
    conversation_id: str | None = None
    context_keys: dict[str, str] = Field(default_factory=dict)
    time_range: str = "last_30_days"


class ChatResponse(BaseModel):
    """Response model for chat analysis."""
    response: str
    conversation_id: str
    provider: str
    model: str
    grounding: dict[str, Any]


class ConversationSummary(BaseModel):
    """Summary of a chat conversation."""
    conversation_id: str
    message_count: int
    last_message_at: str
    preview: str


def _resolve_time_range_days(time_range: str) -> int:
    """Map a chat time-range token to a supported day window."""
    return {
        "last_7_days": 7,
        "last_30_days": 30,
        "last_90_days": 90,
    }.get(time_range, 30)


def _mask_identifier(value: str | None) -> str:
    """Mask sensitive identifiers before sending them to the LLM."""
    if not value:
        return "all"
    if len(value) <= 6:
        return "***"
    return f"{value[:2]}***{value[-4:]}"


async def _load_conversation_history(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
) -> list[dict[str, str]]:
    """Load previous messages for a conversation, capped at MAX_HISTORY_TURNS."""
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.user_id == user_id,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_TURNS)
    )
    rows = result.scalars().all()
    # Reverse to chronological order
    return [{"role": msg.role, "content": msg.content} for msg in reversed(rows)]


@router.post("/analyze", response_model=ChatResponse)
async def analyze_cost_chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    llm_service: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    """
    Analyze cloud costs using AI based on user query.
    
    This endpoint:
    1. Fetches recent cost summary (context)
    2. Loads conversation history if conversation_id is provided
    3. Sends the context + history + user question to the LLM
    4. Persists both messages and returns the response
    """
    if not settings.llm_enabled:
        raise HTTPException(
            status_code=503,
            detail="AI analysis is disabled by runtime policy."
        )

    if llm_service.is_external_provider() and not settings.llm_allow_external_inference:
        raise HTTPException(
            status_code=503,
            detail="AI analysis is blocked because external inference is disabled."
        )

    if llm_service.requires_api_key() and not settings.llm_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM service not configured. Please set LLM_API_KEY."
        )

    # Resolve or create conversation
    conversation_id = request.conversation_id or str(uuid4())

    days = _resolve_time_range_days(request.time_range)
    end_date = datetime.now(timezone.utc)
    start_date = (end_date - timedelta(days=days - 1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    provider_filter = request.context_keys.get("provider")
    account_id = request.context_keys.get("account_id")
    business_unit = request.context_keys.get("business_unit")
    environment = request.context_keys.get("environment")
    cost_center = request.context_keys.get("cost_center")
    service_filter = request.context_keys.get("service")
    region_filter = request.context_keys.get("region")

    filters: list[object] = [
        CloudAccount.organization_id == current_user.organization_id,
        CostRecord.date >= start_date,
        CostRecord.date <= end_date,
    ]

    if provider_filter and provider_filter.lower() != "all":
        filters.append(CloudAccount.provider == provider_filter.lower())

    if account_id and account_id.lower() != "all":
        filters.append(CostRecord.cloud_account_id == account_id)

    if business_unit and business_unit.lower() != "all":
        filters.append(CloudAccount.business_unit == business_unit)

    if environment and environment.lower() != "all":
        filters.append(CloudAccount.environment == environment)

    if cost_center and cost_center.lower() != "all":
        filters.append(CloudAccount.cost_center == cost_center)

    if service_filter and service_filter.lower() != "all":
        filters.append(CostRecord.service == service_filter)

    if region_filter and region_filter.lower() != "all":
        filters.append(CostRecord.region == region_filter)

    account_name: str | None = None
    if account_id and account_id.lower() != "all":
        account_result = await db.execute(
            select(CloudAccount).where(
                CloudAccount.id == account_id,
                CloudAccount.organization_id == current_user.organization_id,
            )
        )
        scoped_account = account_result.scalar_one_or_none()
        account_name = scoped_account.account_name if scoped_account else None

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
        "provider_scope": provider_filter.upper() if provider_filter else "ALL",
        "account_scope": _mask_identifier(account_id),
        "account_name": account_name or "All Accounts",
        "business_unit": business_unit or "all",
        "environment": environment or "all",
        "cost_center": cost_center or "all",
        "service_scope": service_filter or "all",
        "region_scope": region_filter or "all",
        "total_cost": round(float(total_cost or 0), 2),
        "records_found": int(total_records or 0),
        "context_policy": settings.llm_context_policy,
        "top_services": [
            {
                "service": row.service,
                "amount": round(float(row.total), 2),
            }
            for row in service_rows
            if row.service and row.total is not None
        ],
        "daily_trend": [
            {
                "date": row.day.date().isoformat(),
                "amount": round(float(row.total), 2),
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

    # Load conversation history
    history = await _load_conversation_history(
        db, conversation_id, current_user.id
    )

    # Get AI Response
    response_text = await llm_service.get_chat_response(
        message=request.message,
        context_data=context,
        history=history if history else None,
    )

    grounding_data = {
        "time_range": request.time_range,
        "days": days,
        "provider": provider_filter or "all",
        "account_id": account_id or "all",
        "account_name": account_name or "All Accounts",
        "business_unit": business_unit or "all",
        "environment": environment or "all",
        "cost_center": cost_center or "all",
        "service": service_filter or "all",
        "region": region_filter or "all",
        "records_found": context["records_found"],
    }

    # Persist both messages
    db.add(ChatMessage(
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        role="user",
        content=request.message,
    ))
    db.add(ChatMessage(
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        role="assistant",
        content=response_text,
        grounding=grounding_data,
    ))
    await db.commit()

    await AuditService.log(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="CHAT_ANALYZE",
        resource_type="llm",
        details={
            "conversation_id": conversation_id,
            "time_range": request.time_range,
            "provider_scope": provider_filter or "all",
            "account_filter_applied": bool(account_id and account_id.lower() != "all"),
            "business_unit": business_unit or "all",
            "environment": environment or "all",
            "cost_center": cost_center or "all",
            "service_scope": service_filter or "all",
            "region_scope": region_filter or "all",
            "records_found": context["records_found"],
            "history_turns": len(history),
            "llm_provider": settings.llm_provider,
            "llm_execution_mode": "external" if llm_service.is_external_provider() else "local",
            "llm_context_policy": settings.llm_context_policy,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )
    
    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        provider=settings.llm_provider,
        model=settings.llm_model,
        grounding=grounding_data,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    """List recent conversations for the current user."""
    result = await db.execute(
        select(
            ChatMessage.conversation_id,
            func.count(ChatMessage.id).label("message_count"),
            func.max(ChatMessage.created_at).label("last_message_at"),
            func.min(ChatMessage.content).label("first_content"),
        )
        .where(
            ChatMessage.user_id == current_user.id,
            ChatMessage.role == "user",
        )
        .group_by(ChatMessage.conversation_id)
        .order_by(func.max(ChatMessage.created_at).desc())
        .limit(20)
    )
    rows = result.all()

    return [
        ConversationSummary(
            conversation_id=row.conversation_id,
            message_count=row.message_count,
            last_message_at=row.last_message_at.isoformat() if row.last_message_at else "",
            preview=row.first_content[:80] if row.first_content else "",
        )
        for row in rows
    ]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a conversation and all its messages."""
    from sqlalchemy import delete

    await db.execute(
        delete(ChatMessage).where(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.user_id == current_user.id,
        )
    )
    await db.commit()
    return {"status": "deleted", "conversation_id": conversation_id}
